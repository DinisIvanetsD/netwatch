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
from models.event import Event, EventSeverity, EventType
from models.metric import DeviceMetric
from models.scan import Scan, ScanStatus
from models.service import Service
from services.activity import sync_dns_activity
from services.alerts.lifecycle import reconcile_alerts
from services.control.actions import apply_new_device_policy, resume_expired_pauses
from services.control.rules import expire_domain_rules
from services.discovery.base import DiscoveryAdapter, DiscoveryResult
from services.discovery.system import SystemDiscoveryAdapter
from services.realtime.manager import connection_manager
from services.retention import prune_expired_history
from services.scanner.coordinator import scan_coordinator
from services.scanner.tcp import SERVICE_NAMES, tcp_service_scanner

logger = logging.getLogger(__name__)


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
    events: list[PendingEvent] = field(default_factory=list)


def process_discovery_results(
    existing: dict[str, Device],
    results: list[DiscoveryResult],
    now: datetime,
    offline_threshold: int,
) -> ProcessedScan:
    outcome = ProcessedScan()
    observed_addresses: set[str] = set()

    for result in results:
        observed_addresses.add(result.ip_address)
        device = existing.get(result.ip_address)
        discovered_hostname = result.hostname if result.hostname != result.ip_address else None
        if device is None:
            device = Device(
                name=discovered_hostname,
                ip_address=result.ip_address,
                mac_address=result.mac_address,
                hostname=discovered_hostname,
                vendor=None,
                status=DeviceStatus.NEW,
                source=DeviceSource.LIVE,
                latency_ms=result.latency_ms,
                first_seen=now,
                last_seen=now,
                is_gateway=False,
                missed_scans=0,
            )
            outcome.created.append(device)
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
            if device.name == device.ip_address:
                device.name = None
            if device.hostname == device.ip_address:
                device.hostname = None
            device.status = DeviceStatus.ONLINE
            device.last_seen = now
            device.latency_ms = result.latency_ms
            device.mac_address = result.mac_address or device.mac_address
            device.hostname = discovered_hostname or device.hostname
            device.name = device.name or discovered_hostname
            device.missed_scans = 0
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

    for address, device in existing.items():
        if address in observed_addresses:
            continue
        device.missed_scans += 1
        outcome.missed.append(device)
        if device.missed_scans >= offline_threshold and device.status != DeviceStatus.OFFLINE:
            device.status = DeviceStatus.OFFLINE
            device.latency_ms = None
            outcome.events.append(
                PendingEvent(
                    device,
                    EventType.DEVICE_OFFLINE,
                    f"{device.name or device.ip_address} went offline after repeated scan misses.",
                    EventSeverity.MEDIUM,
                    {"missed_scans": device.missed_scans},
                )
            )
    return outcome


def merge_discovery_results(
    existing: dict[str, Device], results: list[DiscoveryResult], now: datetime
) -> list[Device]:
    return process_discovery_results(existing, results, now, 3).created


class ScanService:
    def __init__(self, discovery: DiscoveryAdapter | None = None) -> None:
        self.discovery = discovery or SystemDiscoveryAdapter()

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

            network = ip_network(settings.netwatch_subnet)
            if not isinstance(network, IPv4Network):
                raise ValueError("Only private IPv4 networks are supported")
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
        async with SessionLocal() as session:
            devices = list(
                (
                    await session.scalars(select(Device).where(Device.source == DeviceSource.DEMO))
                ).all()
            )
            count = len(devices)
            now = datetime.now(UTC)
            session.add_all(
                DeviceMetric(
                    device_id=device.id,
                    timestamp=now,
                    latency_ms=device.latency_ms,
                    online=device.status != DeviceStatus.OFFLINE,
                )
                for device in devices
            )
            scan = await session.get(Scan, scan_id)
            if scan is None:
                return
            scan.status = ScanStatus.COMPLETED
            scan.devices_found = count
            scan.finished_at = now
            scan.duration_ms = (perf_counter() - started) * 1000
            await prune_expired_history(session, settings.retention_days)
            await session.commit()
        await connection_manager.broadcast(
            "scan.completed", {"scan_id": scan_id, "devices_found": count}
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
            existing = {
                device.ip_address: device
                for device in (
                    await session.scalars(select(Device).where(Device.source == DeviceSource.LIVE))
                ).all()
            }
            outcome = process_discovery_results(
                existing, results, now, settings.offline_after_missed_scans
            )
            session.add_all(outcome.created)
            await session.flush()
            await apply_new_device_policy(session, outcome.created)

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
                devices=[*existing.values(), *outcome.created],
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
