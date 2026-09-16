import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from ipaddress import IPv4Network, ip_network
from time import perf_counter

from sqlalchemy import select

from core.config import settings
from database.session import SessionLocal
from models.device import Device, DeviceSource, DeviceStatus
from models.device_address import DeviceAddressHistory
from models.event import Event, EventSeverity, EventType
from models.metric import DeviceMetric
from models.scan import Scan, ScanStatus
from models.service import Service
from services.activity import sync_dns_activity
from services.alerts.lifecycle import reconcile_alerts
from services.control.actions import (
    apply_new_device_policy,
    reconcile_network_control_identifiers,
    resume_expired_pauses,
)
from services.control.rules import (
    expire_domain_rules,
    reconcile_all_rules,
    reconcile_device_rules,
)
from services.discovery.base import DiscoveryAdapter, DiscoveryResult
from services.discovery.host_sensor import HostSensorDiscoveryAdapter
from services.discovery.identity import mac_vendor_hint, normalize_mac
from services.discovery.system import SystemDiscoveryAdapter
from services.network_transition import transition_network
from services.realtime.manager import connection_manager
from services.retention import prune_expired_history
from services.scanner.coordinator import scan_coordinator
from services.scanner.reconciliation import consolidate_duplicate_devices
from services.scanner.tcp import SERVICE_NAMES, tcp_service_scanner
from services.simulation import simulation_engine

logger = logging.getLogger(__name__)


def configured_discovery_adapter() -> DiscoveryAdapter:
    if settings.netwatch_host_sensor_url:
        token = settings.effective_host_sensor_token
        if not token:
            raise RuntimeError(
                "NETWATCH_SECRET_KEY or NETWATCH_HOST_SENSOR_TOKEN is required "
                "when the Windows host sensor is configured."
            )
        return HostSensorDiscoveryAdapter(settings.netwatch_host_sensor_url, token)
    return SystemDiscoveryAdapter()


@dataclass(slots=True)
class PendingEvent:
    device: Device
    type: EventType
    message: str
    severity: EventSeverity = EventSeverity.INFO
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessedScan:
    created: list[Device] = field(default_factory=list)
    observed: list[Device] = field(default_factory=list)
    missed: list[Device] = field(default_factory=list)
    displaced: list[Device] = field(default_factory=list)
    ip_changed: list[Device] = field(default_factory=list)
    ip_changes: list[tuple[Device, str]] = field(default_factory=list)
    events: list[PendingEvent] = field(default_factory=list)


def process_discovery_results(
    existing: dict[str, Device] | list[Device],
    results: list[DiscoveryResult],
    now: datetime,
    offline_threshold: int,
    *,
    network_cidr: str | None = None,
    network_id: str | None = None,
) -> ProcessedScan:
    outcome = ProcessedScan()
    observed_devices: set[int] = set()
    active_network_cidr = network_cidr or settings.netwatch_subnet
    active_network_id = network_id or settings.netwatch_network_id
    existing_devices = list(existing.values()) if isinstance(existing, dict) else list(existing)
    existing_by_mac: dict[str, Device] = {}
    existing_by_ip: dict[str, list[Device]] = {}
    for known_device in existing_devices:
        existing_by_ip.setdefault(known_device.ip_address, []).append(known_device)
        normalized = normalize_mac(known_device.mac_address)
        if normalized:
            known_device.mac_address = normalized
            existing_by_mac[normalized] = known_device

    if any(result.is_gateway for result in results):
        for existing_device in existing_devices:
            existing_device.is_gateway = False

    for result in results:
        normalized_mac = normalize_mac(result.mac_address)
        # A stable MAC is stronger evidence than an IP, which DHCP can reassign.
        device = existing_by_mac.get(normalized_mac) if normalized_mac else None
        if device is None:
            candidates = [
                candidate
                for candidate in existing_by_ip.get(result.ip_address, [])
                if id(candidate) not in observed_devices
            ]
            if normalized_mac:
                # A different known MAC at this address is historical evidence for a
                # different device, not a reason to overwrite its identity.
                device = next(
                    (
                        candidate
                        for candidate in candidates
                        if normalize_mac(candidate.mac_address) in {None, normalized_mac}
                    ),
                    None,
                )
            else:
                # Without a MAC, an old IP can belong to more than one historical
                # device. Never silently assign the new observation to an arbitrary
                # owner; create a separate record and keep the ambiguity visible.
                device = candidates[0] if len(candidates) == 1 else None
        if device is not None and id(device) in observed_devices:
            logger.warning(
                "Ignoring duplicate discovery identity for %s at %s",
                normalized_mac or device.ip_address,
                result.ip_address,
            )
            continue
        discovered_hostname = result.hostname if result.hostname != result.ip_address else None
        if device is None:
            device = Device(
                name=discovered_hostname,
                ip_address=result.ip_address,
                mac_address=normalized_mac,
                hostname=discovered_hostname,
                vendor=mac_vendor_hint(result.mac_address),
                status=DeviceStatus.NEW,
                source=DeviceSource.LIVE,
                network_cidr=active_network_cidr,
                network_id=active_network_id,
                latency_ms=result.latency_ms,
                first_seen=now,
                last_seen=now,
                is_gateway=result.is_gateway,
                missed_scans=0,
            )
            outcome.created.append(device)
            existing_by_ip.setdefault(result.ip_address, []).append(device)
            if normalized_mac:
                existing_by_mac[normalized_mac] = device
            outcome.events.append(
                PendingEvent(
                    device,
                    EventType.DEVICE_DISCOVERED,
                    f"{discovered_hostname or result.ip_address} was first discovered.",
                    metadata={"ip_address": result.ip_address},
                )
            )
        else:
            previous_status = device.status
            previous_latency = device.latency_ms
            previous_ip = device.ip_address
            previous_hostname = device.hostname
            if previous_ip != result.ip_address:
                device.ip_address = result.ip_address
                outcome.ip_changed.append(device)
                outcome.ip_changes.append((device, previous_ip))
                outcome.events.append(
                    PendingEvent(
                        device,
                        EventType.DEVICE_UPDATED,
                        f"{device.name or device.hostname or previous_ip} changed IP address.",
                        metadata={
                            "change": "ip_address",
                            "previous_ip": previous_ip,
                            "current_ip": result.ip_address,
                        },
                    )
                )
            if device.name in {previous_ip, result.ip_address}:
                device.name = None
            if device.hostname in {previous_ip, result.ip_address}:
                device.hostname = None
            device.status = DeviceStatus.ONLINE
            device.last_seen = now
            device.latency_ms = result.latency_ms
            device.mac_address = normalized_mac or device.mac_address
            if device.mac_address:
                existing_by_mac[device.mac_address] = device
            device.vendor = device.vendor or mac_vendor_hint(device.mac_address)
            device.hostname = discovered_hostname or device.hostname
            device.name = device.name or discovered_hostname
            device.is_gateway = result.is_gateway or device.is_gateway
            device.missed_scans = 0
            if (
                discovered_hostname
                and previous_hostname
                and discovered_hostname != previous_hostname
            ):
                outcome.events.append(
                    PendingEvent(
                        device,
                        EventType.DEVICE_UPDATED,
                        f"{device.name or device.ip_address} reported a new hostname.",
                        metadata={
                            "change": "hostname",
                            "previous_hostname": previous_hostname,
                            "current_hostname": discovered_hostname,
                        },
                    )
                )
            if previous_status == DeviceStatus.OFFLINE:
                outcome.events.append(
                    PendingEvent(
                        device,
                        EventType.DEVICE_ONLINE,
                        f"{device.name or device.ip_address} came back online.",
                    )
                )
            if (
                previous_latency is not None
                and result.latency_ms is not None
                and result.latency_ms >= 75
                and result.latency_ms >= previous_latency * 3
            ):
                outcome.events.append(
                    PendingEvent(
                        device,
                        EventType.LATENCY_INCREASED,
                        f"{device.name or device.ip_address} latency increased.",
                        EventSeverity.LOW,
                        {"previous_ms": previous_latency, "current_ms": result.latency_ms},
                    )
                )
        outcome.observed.append(device)
        observed_devices.add(id(device))

    observed_by_ip = {device.ip_address: device for device in outcome.observed}
    for device in existing_devices:
        if id(device) in observed_devices:
            continue
        device.missed_scans = (device.missed_scans or 0) + 1
        outcome.missed.append(device)
        replacement = observed_by_ip.get(device.ip_address)
        displaced = replacement is not None and replacement is not device
        if displaced:
            outcome.displaced.append(device)
        if (
            displaced or device.missed_scans >= offline_threshold
        ) and device.status != DeviceStatus.OFFLINE:
            device.status = DeviceStatus.OFFLINE
            device.latency_ms = None
            outcome.events.append(
                PendingEvent(
                    device,
                    EventType.DEVICE_OFFLINE,
                    (
                        f"{device.name or device.ip_address} went offline because its address "
                        "is now used by another device."
                        if displaced
                        else f"{device.name or device.ip_address} went offline after repeated "
                        "scan misses."
                    ),
                    EventSeverity.MEDIUM,
                    {
                        "missed_scans": device.missed_scans,
                        "address_reassigned": displaced,
                    },
                )
            )
    return outcome


def merge_discovery_results(
    existing: dict[str, Device], results: list[DiscoveryResult], now: datetime
) -> list[Device]:
    return process_discovery_results(existing, results, now, 3).created


class ScanService:
    def __init__(self, discovery: DiscoveryAdapter | None = None) -> None:
        self.discovery = discovery or configured_discovery_adapter()
        self.last_environment = None

    async def _network_for_scan(self, scan_id: int) -> IPv4Network:
        configured = ip_network(settings.netwatch_subnet)
        if not isinstance(configured, IPv4Network):
            raise ValueError("Only private IPv4 networks are supported")
        try:
            environment = await self.discovery.detect_network()
        except Exception:
            if settings.auto_detect_network:
                raise
            logger.warning("Could not read optional discovery environment", exc_info=True)
            environment = None
        if not settings.auto_detect_network:
            if environment is not None and environment.subnet == str(configured):
                self.last_environment = environment
                desired_network_id = environment.network_id or settings.netwatch_network_id
            else:
                self.last_environment = None
                desired_network_id = settings.netwatch_network_id
            async with SessionLocal() as session:
                await transition_network(
                    session,
                    subnet=str(configured),
                    network_id=desired_network_id,
                    source=DeviceSource.LIVE,
                    actor="scanner",
                    scan_id=scan_id,
                    interface_name=(
                        environment.interface_name if self.last_environment is not None else None
                    ),
                )
            return configured
        if environment is None:
            raise RuntimeError(
                "Automatic network detection requires the NetWatch Windows host sensor. "
                "Start the sensor or disable automatic detection in Settings."
            )
        if environment.network_id is None:
            raise RuntimeError(
                "The host sensor could not verify the physical network identity. "
                "NetWatch stopped the scan to prevent carrying IP controls to another LAN."
            )
        detected = ip_network(environment.subnet)
        if not isinstance(detected, IPv4Network):
            raise RuntimeError("The host sensor did not return a private IPv4 network.")
        detected_subnet = str(detected)
        async with SessionLocal() as session:
            await transition_network(
                session,
                subnet=detected_subnet,
                network_id=environment.network_id,
                source=DeviceSource.LIVE,
                actor="scanner",
                scan_id=scan_id,
                interface_name=environment.interface_name,
            )
        self.last_environment = environment
        return detected

    async def run(self, scan_id: int) -> None:
        started = perf_counter()
        try:
            async with SessionLocal() as session:
                scan = await session.get(Scan, scan_id)
                if scan is None:
                    return
                scan.status = ScanStatus.RUNNING
                scan.started_at = datetime.now(UTC)
                await session.commit()

            await connection_manager.broadcast("scan.started", {"scan_id": scan_id})

            if settings.netwatch_demo_mode:
                await self._complete_demo_scan(scan_id, started)
                return

            network = await self._network_for_scan(scan_id)
            if isinstance(self.discovery, HostSensorDiscoveryAdapter):
                expected_network_id = (
                    self.last_environment.network_id
                    if self.last_environment is not None
                    else settings.netwatch_network_id
                )
                results = await self.discovery.discover(
                    network,
                    expected_network_id=expected_network_id,
                )
                # The host can change Wi-Fi/hotspot while a scan is in flight.
                # Verify the environment again before persisting any observation,
                # including the same-CIDR case where the subnet alone is useless.
                after_scan = await self.discovery.detect_network()
                if after_scan.network_id != expected_network_id or after_scan.subnet != str(
                    network
                ):
                    raise RuntimeError(
                        "The Windows host changed physical networks during the scan. "
                        "No devices were saved from this scan."
                    )
                self.last_environment = after_scan
            else:
                results = await self.discovery.discover(network)
            service_results: dict[str, set[int]] | None = None
            if settings.service_scan_enabled:
                service_results = await tcp_service_scanner.scan(
                    (result.ip_address for result in results),
                    settings.approved_service_ports,
                    settings.scan_concurrency,
                )
            await self._persist_results(scan_id, results, service_results, started)
        except asyncio.CancelledError:
            await self._mark_cancelled(scan_id, started)
            raise
        except Exception as error:
            logger.exception("Network scan %s failed", scan_id)
            await self._mark_failed(scan_id, started, str(error))
        finally:
            await scan_coordinator.release()

    async def _complete_demo_scan(self, scan_id: int, started: float) -> None:
        # A manual scan in simulation mode runs one visible simulation step so the
        # dashboard reflects the sweep instead of a no-op completion record.
        outcome = await simulation_engine.tick()
        async with SessionLocal() as session:
            scan = await session.get(Scan, scan_id)
            if scan is None:
                return
            now = datetime.now(UTC)
            scan.status = ScanStatus.COMPLETED
            scan.devices_found = outcome.online_devices
            scan.finished_at = now
            scan.duration_ms = (perf_counter() - started) * 1000
            await prune_expired_history(session, settings.retention_days)
            await session.commit()
        await connection_manager.broadcast(
            "scan.completed", {"scan_id": scan_id, "devices_found": outcome.online_devices}
        )

    async def _persist_results(
        self,
        scan_id: int,
        results: list[DiscoveryResult],
        service_results: dict[str, set[int]] | None,
        started: float,
    ) -> None:
        now = datetime.now(UTC)
        async with SessionLocal() as session:
            scoped_devices = list(
                (
                    await session.scalars(
                        select(Device).where(
                            Device.source == DeviceSource.LIVE,
                            Device.network_cidr == settings.netwatch_subnet,
                            Device.network_id == settings.netwatch_network_id,
                        )
                    )
                ).all()
            )
            scoped_devices, _ = await consolidate_duplicate_devices(session, scoped_devices)
            outcome = process_discovery_results(
                scoped_devices,
                results,
                now,
                settings.offline_after_missed_scans,
                network_cidr=settings.netwatch_subnet,
                network_id=settings.netwatch_network_id,
            )
            session.add_all(outcome.created)
            await session.flush()
            session.add_all(
                DeviceAddressHistory(
                    device_id=device.id,
                    ip_address=device.ip_address,
                    network_cidr=device.network_cidr,
                    network_id=device.network_id,
                    started_at=device.first_seen,
                )
                for device in outcome.created
            )
            for device, previous_ip in outcome.ip_changes:
                current_history = await session.scalar(
                    select(DeviceAddressHistory)
                    .where(
                        DeviceAddressHistory.device_id == device.id,
                        DeviceAddressHistory.ip_address == previous_ip,
                        DeviceAddressHistory.ended_at.is_(None),
                    )
                    .order_by(DeviceAddressHistory.started_at.desc())
                )
                if current_history is not None:
                    current_history.ended_at = now
                session.add(
                    DeviceAddressHistory(
                        device_id=device.id,
                        ip_address=device.ip_address,
                        network_cidr=device.network_cidr,
                        network_id=device.network_id,
                        started_at=now,
                    )
                )
            # A different MAC at an address means the lease moved to another
            # device. Close the displaced owner's active window as well, or all
            # later DNS records for the reused address would remain ambiguous.
            for device in outcome.displaced:
                displaced_histories = list(
                    (
                        await session.scalars(
                            select(DeviceAddressHistory).where(
                                DeviceAddressHistory.device_id == device.id,
                                DeviceAddressHistory.ip_address == device.ip_address,
                                DeviceAddressHistory.network_cidr == device.network_cidr,
                                DeviceAddressHistory.network_id == device.network_id,
                                DeviceAddressHistory.ended_at.is_(None),
                            )
                        )
                    ).all()
                )
                for history in displaced_histories:
                    history.ended_at = now
            await apply_new_device_policy(session, outcome.created)

            await reconcile_network_control_identifiers(
                session,
                [*scoped_devices, *outcome.created],
                observed_device_ids={
                    device.id for device in outcome.observed if device.id is not None
                },
            )
            for device in outcome.ip_changed:
                await reconcile_device_rules(session, device.id, DeviceSource.LIVE)
            await reconcile_all_rules(session, DeviceSource.LIVE)

            if service_results is not None:
                observed_ids = [device.id for device in outcome.observed]
                known_services = {
                    (service.device_id, service.port): service
                    for service in (
                        await session.scalars(
                            select(Service).where(Service.device_id.in_(observed_ids))
                        )
                    ).all()
                }
                for device in outcome.observed:
                    self._merge_service_observations(
                        device,
                        service_results.get(device.ip_address, set()),
                        known_services,
                        outcome,
                        now,
                        session,
                    )

            session.add_all(
                DeviceMetric(
                    device_id=device.id,
                    timestamp=now,
                    latency_ms=device.latency_ms,
                    online=True,
                )
                for device in outcome.observed
            )
            session.add_all(
                DeviceMetric(device_id=device.id, timestamp=now, latency_ms=None, online=False)
                for device in outcome.missed
            )
            persisted_events = [
                Event(
                    device_id=pending.device.id,
                    type=pending.type,
                    message=pending.message,
                    severity=pending.severity,
                    timestamp=now,
                    metadata_payload=pending.metadata,
                    source=DeviceSource.LIVE,
                )
                for pending in outcome.events
            ]
            session.add_all(persisted_events)
            await session.flush()
            persisted_alerts = await reconcile_alerts(
                session,
                source=DeviceSource.LIVE,
                devices=[*scoped_devices, *outcome.created],
                services=known_services.values() if service_results is not None else [],
                events=persisted_events,
            )
            session.add_all(persisted_alerts)
            scan = await session.get(Scan, scan_id)
            if scan is None:
                return
            scan.status = ScanStatus.COMPLETED
            scan.devices_found = len(results)
            scan.finished_at = now
            scan.duration_ms = (perf_counter() - started) * 1000
            await expire_domain_rules(session, DeviceSource.LIVE)
            await resume_expired_pauses(session, DeviceSource.LIVE)
            await prune_expired_history(session, settings.retention_days)
            await session.commit()

        for event in persisted_events:
            await connection_manager.broadcast(
                event.type.value,
                {"event_id": event.id, "device_id": event.device_id, "message": event.message},
            )
        for alert in persisted_alerts:
            await connection_manager.broadcast(
                "alert.created",
                {
                    "alert_id": alert.id,
                    "device_id": alert.device_id,
                    "title": alert.title,
                    "severity": alert.severity.value,
                },
            )
        internet_activity_added = await sync_dns_activity()
        await connection_manager.broadcast(
            "scan.completed",
            {
                "scan_id": scan_id,
                "devices_found": len(results),
                "internet_activity_added": internet_activity_added,
            },
        )

    @staticmethod
    def _merge_service_observations(
        device: Device,
        open_ports: set[int],
        known_services: dict[tuple[int, int], Service],
        outcome: ProcessedScan,
        now: datetime,
        session: object,
    ) -> None:
        for port in open_ports:
            service = known_services.get((device.id, port))
            if service is None:
                session.add(
                    Service(
                        device_id=device.id,
                        port=port,
                        protocol="tcp",
                        service_name=SERVICE_NAMES.get(port, f"TCP {port}"),
                        first_seen=now,
                        last_seen=now,
                        active=True,
                    )
                )
                outcome.events.append(
                    PendingEvent(
                        device,
                        EventType.SERVICE_DISCOVERED,
                        f"TCP {port} / {SERVICE_NAMES.get(port, 'Unknown')} was newly observed.",
                        EventSeverity.LOW,
                        {"port": port, "protocol": "tcp"},
                    )
                )
            elif service.active:
                service.active = True
                service.last_seen = now
            else:
                service.active = True
                service.last_seen = now
                outcome.events.append(
                    PendingEvent(
                        device,
                        EventType.SERVICE_DISCOVERED,
                        f"TCP {port} / {service.service_name} was observed again.",
                        EventSeverity.LOW,
                        {"port": port, "protocol": "tcp"},
                    )
                )
        for (device_id, port), service in known_services.items():
            if device_id == device.id and service.active and port not in open_ports:
                service.active = False
                outcome.events.append(
                    PendingEvent(
                        device,
                        EventType.SERVICE_REMOVED,
                        f"TCP {port} / {service.service_name} is no longer observed.",
                        metadata={"port": port, "protocol": "tcp"},
                    )
                )

    async def _mark_failed(self, scan_id: int, started: float, message: str) -> None:
        async with SessionLocal() as session:
            scan = await session.get(Scan, scan_id)
            if scan is not None:
                scan.status = ScanStatus.FAILED
                scan.finished_at = datetime.now(UTC)
                scan.duration_ms = (perf_counter() - started) * 1000
                scan.error = message[:1000]
                await session.commit()
        await connection_manager.broadcast("scan.failed", {"scan_id": scan_id})

    async def _mark_cancelled(self, scan_id: int, started: float) -> None:
        async with SessionLocal() as session:
            scan = await session.get(Scan, scan_id)
            if scan is not None:
                scan.status = ScanStatus.CANCELLED
                scan.finished_at = datetime.now(UTC)
                scan.duration_ms = (perf_counter() - started) * 1000
                await session.commit()


scan_service = ScanService()
