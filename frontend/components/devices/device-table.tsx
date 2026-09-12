import Link from "next/link";
import { ArrowDown, ArrowUp, Router } from "lucide-react";

import { DeviceStatusBadge } from "@/components/devices/device-status-badge";
import { EmptyState } from "@/components/empty-state";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  deviceDisplayName,
  formatLatency,
  formatRelativeTime,
  hasAssignedDeviceName,
} from "@/lib/format";
import type { Device, DeviceQuery } from "@/types/device";

type SortField = NonNullable<DeviceQuery["sortBy"]>;

interface DeviceTableProps {
  devices: Device[];
  sortBy: SortField;
  sortOrder: "asc" | "desc";
  query: Record<string, string | undefined>;
  filtered: boolean;
}

function buildQuery(
  query: Record<string, string | undefined>,
  overrides: Record<string, string | undefined>,
) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries({ ...query, ...overrides })) {
    if (value) params.set(key, value);
  }
  return `/devices?${params.toString()}`;
}

function SortHeading({
  label,
  field,
  sortBy,
  sortOrder,
  query,
}: {
  label: string;
  field: SortField;
  sortBy: SortField;
  sortOrder: "asc" | "desc";
  query: Record<string, string | undefined>;
}) {
  const active = sortBy === field;
  const nextOrder = active && sortOrder === "asc" ? "desc" : "asc";
  const Icon = sortOrder === "asc" ? ArrowUp : ArrowDown;

  return (
    <Link
      href={buildQuery(query, {
        sort_by: field,
        sort_order: nextOrder,
        page: undefined,
      })}
      className="hover:text-foreground inline-flex items-center gap-1.5"
      aria-label={`Sort devices by ${label}`}
    >
      {label}
      {active ? <Icon className="size-3" aria-hidden="true" /> : null}
    </Link>
  );
}

export function DeviceTable({
  devices,
  sortBy,
  sortOrder,
  query,
  filtered,
}: DeviceTableProps) {
  if (devices.length === 0) {
    return (
      <EmptyState
        icon={Router}
        title={
          filtered
            ? "No devices match these filters"
            : "No devices discovered yet"
        }
        description={
          filtered
            ? "Try a different search term or status filter."
            : "Run your first authorized network scan to build the device inventory."
        }
      />
    );
  }

  return (
    <Card className="overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead scope="col">Status</TableHead>
            <TableHead scope="col">
              <SortHeading
                label="Device"
                field="name"
                sortBy={sortBy}
                sortOrder={sortOrder}
                query={query}
              />
            </TableHead>
            <TableHead className="hidden md:table-cell">
              <SortHeading
                label="IP Address"
                field="ip_address"
                sortBy={sortBy}
                sortOrder={sortOrder}
                query={query}
              />
            </TableHead>
            <TableHead scope="col" className="hidden md:table-cell">
              MAC Address
            </TableHead>
            <TableHead scope="col" className="hidden lg:table-cell">
              Vendor
            </TableHead>
            <TableHead scope="col" className="hidden lg:table-cell">
              <SortHeading
                label="Latency"
                field="latency_ms"
                sortBy={sortBy}
                sortOrder={sortOrder}
                query={query}
              />
            </TableHead>
            <TableHead scope="col" className="hidden xl:table-cell">
              Services
            </TableHead>
            <TableHead scope="col" className="hidden lg:table-cell">
              <SortHeading
                label="Last Seen"
                field="last_seen"
                sortBy={sortBy}
                sortOrder={sortOrder}
                query={query}
              />
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {devices.map((device) => (
            <TableRow key={device.id} className="align-top">
              <TableCell>
                <DeviceStatusBadge status={device.status} />
              </TableCell>
              <TableCell>
                <Link
                  href={`/devices/${device.id}${hasAssignedDeviceName(device) ? "" : "?tab=access"}`}
                  className="group block"
                >
                  <span className="text-foreground group-hover:text-primary font-medium">
                    {deviceDisplayName(device)}
                  </span>
                  <span className="text-muted-foreground mt-1 block text-xs">
                    {device.owner ?? "Owner not assigned"} ·{" "}
                    {device.device_type ?? "Type unknown"}
                  </span>
                  <span className="text-muted-foreground mt-0.5 block text-xs">
                    {device.hostname ?? "Hostname unavailable"}
                  </span>
                  {!hasAssignedDeviceName(device) ? (
                    <span className="text-primary mt-1 block text-[10px] font-semibold tracking-wider uppercase">
                      Name this device
                    </span>
                  ) : null}
                  {device.is_gateway ? (
                    <span className="text-muted-foreground mt-0.5 block text-[10px] tracking-wider uppercase">
                      Gateway
                    </span>
                  ) : null}
                  <span className="text-muted-foreground mt-1 block font-mono text-[11px] md:hidden">
                    {device.ip_address} ·{" "}
                    {device.mac_address ?? "MAC unavailable"}
                  </span>
                </Link>
              </TableCell>
              <TableCell className="hidden font-mono text-xs md:table-cell">
                {device.ip_address}
              </TableCell>
              <TableCell className="text-muted-foreground hidden font-mono text-xs md:table-cell">
                {device.mac_address ?? "—"}
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                {device.vendor ?? "Unknown"}
              </TableCell>
              <TableCell className="hidden font-mono text-xs lg:table-cell">
                {formatLatency(device.latency_ms)}
              </TableCell>
              <TableCell className="hidden font-mono text-xs xl:table-cell">
                {device.service_ports.length
                  ? device.service_ports.join(", ")
                  : "—"}
              </TableCell>
              <TableCell
                className="hidden lg:table-cell"
                title={new Date(device.last_seen).toLocaleString()}
                suppressHydrationWarning
              >
                {formatRelativeTime(device.last_seen)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
