import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from ipaddress import ip_network
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import settings
from database.session import SessionLocal
from models.alert import Alert
from models.device import Device, DeviceSource, DeviceStatus
from models.event import Event, EventSeverity, EventType
from models.metric import DeviceMetric
from models.service import Service
from services.alerts.lifecycle import reconcile_alerts
from services.realtime.manager import connection_manager
from services.retention import prune_expired_history
from services.scanner.tcp import SERVICE_NAMES

logger = logging.getLogger(__name__)

TICK_SECONDS = 15
LATENCY_ALERT_THRESHOLD_MS = 75.0
ARRIVAL_CHANCE = 0.15
OFFLINE_CHANCE = 0.10
RECOVERY_CHANCE = 0.35
MIN_SIMULATED_LATENCY_MS = 0.8
MAX_SIMULATED_LATENCY_MS = 180.0


@dataclass(frozen=True, slots=True)
class SimulatedArrival:
    """A virtual device that can join the simulated network while it runs."""

    name: str
    hostname: str
    mac_address: str
    vendor: str
    device_type: str
    owner: str | None
    trust_state: str
    base_latency_ms: float
    ports: tuple[int, ...] = ()


SIMULATED_ARRIVALS: tuple[SimulatedArrival, ...] = (
    SimulatedArrival(
        "Guest-Phone",
        "guest-phone.netwatch.sim",
        "02:11:22:AA:10:21",
        "Xiaomi Communications",
        "phone",
        None,
        "unknown",
        26.0,
    ),
    SimulatedArrival(
        "Smart-Speaker",
        "smart-speaker.netwatch.sim",
        "02:11:22:AA:10:22",
        "Amazon",
        "speaker",
        None,
        "trusted",
        14.0,
        (80, 443),
    ),
    SimulatedArrival(
        "Work-Laptop",
        "work-laptop.netwatch.sim",
        "02:11:22:AA:10:23",
        "Dell",
        "laptop",
        "Dinis",
        "trusted",
        5.0,
        (22, 3389),
    ),
    SimulatedArrival(
        "IoT-Plug",
        "iot-plug.netwatch.sim",
        "02:11:22:AA:10:24",
        "TP-Link",
        "iot",
        None,
        "unknown",
        31.0,
    ),
    SimulatedArrival(
        "Handheld-Console",
        "console.netwatch.sim",
        "02:11:22:AA:10:25",
        "Nintendo",
        "game_console",
        None,
        "trusted",
        11.0,
    ),
)


@dataclass(slots=True)
class PendingSimulationEvent:
    device: Device
    type: EventType
    message: str
    severity: EventSeverity = EventSeverity.INFO
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class SimulationTick:
    """What one simulation step changed, so callers can report it honestly."""

    devices: int = 0
    online_devices: int = 0
    created: list[Device] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)


def operating_mode() -> Literal["simulation", "live"]:
    """Return the user-facing mode name for the current demo/live configuration."""

    return "simulation" if settings.netwatch_demo_mode else "live"


class SimulationEngine:
    """Evolve the simulated network so the dashboard behaves like a live LAN.

    The engine only touches devices with the DEMO source inside the current
    network scope, so simulated inventory can never mix with real scans.
    """

    def __init__(
        self,
        *,
        seed: int | None = None,
        session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
    ) -> None:
        self._rng = random.Random(seed)
        self._session_factory = session_factory
        self._task: asyncio.Task[None] | None = None
        self._tick_lock = asyncio.Lock()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="netwatch-simulation")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(TICK_SECONDS)
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("The network simulation tick failed")

    async def tick(self) -> SimulationTick:
        """Run one simulation step. A tick that overlaps another one is skipped."""
        if self._tick_lock.locked():
            return SimulationTick()
        async with self._tick_lock:
            return await self._simulate()

    def _next_latency(self, current: float | None, base: float) -> float:
        anchor = current if current is not None else base
        drifted = anchor + self._rng.uniform(-6.0, 6.0)
        return round(min(MAX_SIMULATED_LATENCY_MS, max(MIN_SIMULATED_LATENCY_MS, drifted)), 1)

    def _advance_device(
        self,
        device: Device,
        now: datetime,
        pending: list[PendingSimulationEvent],
    ) -> None:
        label = device.name or device.hostname or device.ip_address
        if device.is_gateway:
            # The simulated gateway stays online; a flapping router hides other changes.
            device.latency_ms = self._next_latency(device.latency_ms, 2.5)
            device.missed_scans = 0
            device.last_seen = now
            return
        if device.status == DeviceStatus.OFFLINE:
            if self._rng.random() >= RECOVERY_CHANCE:
                device.missed_scans += 1
                return
            device.status = DeviceStatus.ONLINE
            device.missed_scans = 0
            device.latency_ms = self._next_latency(None, 8.0)
            device.last_seen = now
            pending.append(
                PendingSimulationEvent(
                    device,
                    EventType.DEVICE_ONLINE,
                    f"{label} came back online on the simulated network.",
                )
            )
            return
        if self._rng.random() < OFFLINE_CHANCE:
            device.status = DeviceStatus.OFFLINE
            device.latency_ms = None
            pending.append(
                PendingSimulationEvent(
                    device,
                    EventType.DEVICE_OFFLINE,
                    f"{label} went offline on the simulated network.",
                    EventSeverity.MEDIUM,
                )
            )
            return
        previous_latency = device.latency_ms
        device.latency_ms = self._next_latency(previous_latency, 8.0)
        device.missed_scans = 0
        device.last_seen = now
        if (
            previous_latency is not None
            and previous_latency < LATENCY_ALERT_THRESHOLD_MS <= device.latency_ms
        ):
            pending.append(
                PendingSimulationEvent(
                    device,
                    EventType.LATENCY_INCREASED,
                    f"{label} latency increased to {device.latency_ms} ms.",
                    EventSeverity.MEDIUM,
                )
            )

    async def _maybe_add_arrival(
        self,
        session: AsyncSession,
        devices: list[Device],
        now: datetime,
        pending: list[PendingSimulationEvent],
    ) -> list[Device]:
        if self._rng.random() >= ARRIVAL_CHANCE:
            return []
        known_macs = {device.mac_address for device in devices}
        available = [
            arrival for arrival in SIMULATED_ARRIVALS if arrival.mac_address not in known_macs
        ]
        if not available:
            return []
        arrival = self._rng.choice(available)
        used_ips = {device.ip_address for device in devices}
        network = ip_network(settings.netwatch_subnet)
        address = next((str(host) for host in network.hosts() if str(host) not in used_ips), None)
        if address is None:
            return []
        device = Device(
            name=arrival.name,
            ip_address=address,
            mac_address=arrival.mac_address,
            hostname=arrival.hostname,
            vendor=arrival.vendor,
            status=DeviceStatus.NEW,
            source=DeviceSource.DEMO,
            network_cidr=settings.netwatch_subnet,
            network_id=settings.netwatch_network_id,
            latency_ms=arrival.base_latency_ms,
            first_seen=now,
            last_seen=now,
            missed_scans=0,
            device_type=arrival.device_type,
            owner=arrival.owner,
            trust_state=arrival.trust_state,
        )
        session.add(device)
        await session.flush()
        pending.append(
            PendingSimulationEvent(
                device,
                EventType.DEVICE_DISCOVERED,
                f"{arrival.name} joined the simulated network.",
                metadata={"ip_address": address, "simulated": True},
            )
        )
        for port in arrival.ports:
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
            pending.append(
                PendingSimulationEvent(
                    device,
                    EventType.SERVICE_DISCOVERED,
                    f"TCP {port} / {SERVICE_NAMES.get(port, 'Unknown')} was newly observed.",
                    EventSeverity.LOW,
                    {"port": port, "protocol": "tcp"},
                )
            )
        return [device]

    async def _simulate(self) -> SimulationTick:
        now = datetime.now(UTC)
        outcome = SimulationTick()
        async with self._session_factory() as session:
            devices = list(
                (
                    await session.scalars(
                        select(Device)
                        .where(
                            Device.source == DeviceSource.DEMO,
                            Device.network_cidr == settings.netwatch_subnet,
                            Device.network_id == settings.netwatch_network_id,
                        )
                        .order_by(Device.ip_address)
                    )
                ).all()
            )
            pending: list[PendingSimulationEvent] = []
            for device in devices:
                self._advance_device(device, now, pending)
            outcome.created = await self._maybe_add_arrival(session, devices, now, pending)
            await session.flush()

            every_device = [*devices, *outcome.created]
            session.add_all(
                DeviceMetric(
                    device_id=device.id,
                    timestamp=now,
                    latency_ms=(
                        device.latency_ms if device.status != DeviceStatus.OFFLINE else None
                    ),
                    online=device.status != DeviceStatus.OFFLINE,
                )
                for device in every_device
            )
            outcome.events = [
                Event(
                    device_id=item.device.id,
                    type=item.type,
                    message=item.message,
                    severity=item.severity,
                    timestamp=now,
                    metadata_payload=item.metadata,
                    source=DeviceSource.DEMO,
                )
                for item in pending
            ]
            session.add_all(outcome.events)
            await session.flush()

            device_ids = [device.id for device in every_device if device.id is not None]
            services: list[Service] = []
            if device_ids:
                services = list(
                    (
                        await session.scalars(
                            select(Service).where(
                                Service.active.is_(True),
                                Service.device_id.in_(device_ids),
                            )
                        )
                    ).all()
                )
            outcome.alerts = await reconcile_alerts(
                session,
                source=DeviceSource.DEMO,
                devices=every_device,
                services=services,
                events=outcome.events,
            )
            session.add_all(outcome.alerts)
            await prune_expired_history(session, settings.retention_days)
            await session.commit()

            outcome.devices = len(every_device)
            outcome.online_devices = sum(
                1 for device in every_device if device.status != DeviceStatus.OFFLINE
            )

        for event in outcome.events:
            await connection_manager.broadcast(
                event.type.value,
                {"event_id": event.id, "device_id": event.device_id, "message": event.message},
            )
        for alert in outcome.alerts:
            await connection_manager.broadcast(
                "alert.created",
                {
                    "alert_id": alert.id,
                    "device_id": alert.device_id,
                    "title": alert.title,
                    "severity": alert.severity.value,
                },
            )
        await connection_manager.broadcast(
            "simulation.updated",
            {"devices": outcome.devices, "online_devices": outcome.online_devices},
        )
        return outcome


simulation_engine = SimulationEngine()
