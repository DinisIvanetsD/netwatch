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
            <TableHead>
              <SortHeading
                label="IP Address"
                field="ip_address"
                sortBy={sortBy}
                sortOrder={sortOrder}
                query={query}
              />
            </TableHead>
            <TableHead scope="col">MAC Address</TableHead>
            <TableHead scope="col">Vendor</TableHead>
            <TableHead scope="col">
              <SortHeading
                label="Latency"
                field="latency_ms"
                sortBy={sortBy}
                sortOrder={sortOrder}
                query={query}
              />
            </TableHead>
            <TableHead scope="col">Services</TableHead>
            <TableHead scope="col">
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
            <TableRow key={device.id}>
              <TableCell>
                <DeviceStatusBadge status={device.status} />
              </TableCell>
              <TableCell>
                <Link
                  href={`/devices/${device.id}${deviceDisplayName(device) === "Unnamed device" ? "?tab=access" : ""}`}
                  className="group block"
                >
                  <span className="text-foreground group-hover:text-primary font-medium">
                    {deviceDisplayName(device)}
                  </span>
                  {device.is_gateway ? (
                    <span className="text-muted-foreground mt-0.5 block text-[10px] tracking-wider uppercase">
                      Gateway
                    </span>
                  ) : deviceDisplayName(device) === "Unnamed device" ? (
                    <span className="text-primary mt-0.5 block text-[10px] tracking-wider uppercase">
                      Set name and owner
                    </span>
                  ) : null}
                  {device.owner ? (
                    <span className="text-muted-foreground mt-0.5 block text-xs">
                      Owner: {device.owner}
                    </span>
                  ) : null}
                </Link>
              </TableCell>
              <TableCell className="font-mono text-xs">
                {device.ip_address}
              </TableCell>
              <TableCell className="text-muted-foreground font-mono text-xs">
                {device.mac_address ?? "—"}
              </TableCell>
              <TableCell>{device.vendor ?? "Unknown"}</TableCell>
              <TableCell className="font-mono text-xs">
                {formatLatency(device.latency_ms)}
              </TableCell>
              <TableCell className="font-mono text-xs">
                {device.service_ports.length
                  ? device.service_ports.join(", ")
                  : "—"}
              </TableCell>
              <TableCell title={new Date(device.last_seen).toLocaleString()}>
                {formatRelativeTime(device.last_seen)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
