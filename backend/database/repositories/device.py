from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.device import Device, DeviceSource, DeviceStatus
from schemas.device import DeviceSortField, SortOrder


class DeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        *,
        source: DeviceSource,
        network_cidr: str,
        network_id: str,
        page: int,
        per_page: int,
        status: DeviceStatus | None,
        search: str | None,
        sort_by: DeviceSortField,
        sort_order: SortOrder,
    ) -> tuple[list[Device], int]:
        filters = [
            Device.source == source,
            Device.network_cidr == network_cidr,
            Device.network_id == network_id,
        ]
        if status is not None:
            filters.append(Device.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Device.name.ilike(pattern),
                    Device.hostname.ilike(pattern),
                    Device.ip_address.ilike(pattern),
                    Device.mac_address.ilike(pattern),
                    Device.vendor.ilike(pattern),
                )
            )

        sort_columns = {
            DeviceSortField.NAME: func.coalesce(Device.name, Device.hostname, Device.ip_address),
            DeviceSortField.IP_ADDRESS: Device.ip_address,
            DeviceSortField.STATUS: Device.status,
            DeviceSortField.LATENCY: Device.latency_ms,
            DeviceSortField.LAST_SEEN: Device.last_seen,
        }
        sort_column = sort_columns[sort_by]
        ordering = sort_column.asc() if sort_order == SortOrder.ASC else sort_column.desc()

        query: Select[tuple[Device]] = (
            select(Device)
            .where(*filters)
            .order_by(ordering, Device.id.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        count_query = select(func.count()).select_from(Device).where(*filters)

        devices = list((await self.session.scalars(query)).all())
        total = int((await self.session.scalar(count_query)) or 0)
        return devices, total

    async def get(
        self,
        device_id: int,
        *,
        source: DeviceSource,
        network_cidr: str,
        network_id: str,
    ) -> Device | None:
        return await self.session.scalar(
            select(Device).where(
                Device.id == device_id,
                Device.source == source,
                Device.network_cidr == network_cidr,
                Device.network_id == network_id,
            )
        )
