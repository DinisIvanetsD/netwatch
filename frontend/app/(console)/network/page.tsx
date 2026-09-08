import Link from "next/link";
import { Activity, Network, Router, ServerCog } from "lucide-react";
import { DeviceStatusBadge } from "@/components/devices/device-status-badge";
import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getDevices, getNetworkStatus } from "@/lib/api";
import { formatLatency, formatRelativeTime } from "@/lib/format";

export const metadata = { title: "Network" };

export const dynamic = "force-dynamic";

export default async function NetworkPage() {
  const [network, devices] = await Promise.all([
    getNetworkStatus(),
    getDevices({ perPage: 100, sortBy: "ip_address", sortOrder: "asc" }),
  ]);
  const gateway = devices.items.find((device) => device.is_gateway);
  const peers = devices.items.filter((device) => !device.is_gateway);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Network</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Verified LAN scope, monitoring health, and discovered devices.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="DISCOVERED"
          value={String(network.total_devices)}
          detail={network.subnet}
          icon={ServerCog}
        />
        <MetricCard
          label="ONLINE"
          value={String(network.online_devices)}
          detail={`${network.total_devices ? Math.round((network.online_devices / network.total_devices) * 100) : 0}% availability`}
          icon={Activity}
          tone="success"
        />
        <MetricCard
          label="AVG LATENCY"
          value={formatLatency(network.average_latency_ms)}
          detail="Online devices"
          icon={Network}
        />
        <MetricCard
          label="SCANNER"
          value={network.scan_running ? "Running" : "Ready"}
          detail={
            network.last_completed_scan
              ? `Last ${formatRelativeTime(network.last_completed_scan)}`
              : "No completed scan"
          }
          icon={Router}
        />
      </div>
      {devices.items.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Gateway-centered LAN map</CardTitle>
            <p className="text-muted-foreground text-xs">
              Discovery membership only; physical links are not inferred.
            </p>
          </CardHeader>
          <CardContent className="space-y-8">
            <div className="mx-auto flex max-w-xs flex-col items-center">
              <span className="bg-primary/10 text-primary rounded-xl p-3">
                <Router className="size-6" aria-hidden="true" />
              </span>
              <p className="mt-2 text-sm font-semibold">
                {gateway?.name ?? "Gateway"}
              </p>
              <p className="text-muted-foreground font-mono text-xs">
                {gateway?.ip_address ?? network.gateway ?? "Not detected"}
              </p>
              <div className="bg-border mt-4 h-8 w-px" />
            </div>
            <div className="border-border grid gap-3 border-t pt-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {peers.map((device) => (
                <Link
                  key={device.id}
                  href={`/devices/${device.id}`}
                  className="border-border hover:border-primary/30 bg-muted/20 rounded-lg border p-4 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">
                      {device.name ?? device.hostname ?? device.ip_address}
                    </span>
                    <DeviceStatusBadge status={device.status} />
                  </div>
                  <p className="text-muted-foreground mt-2 font-mono text-xs">
                    {device.ip_address}
                  </p>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          icon={Network}
          title="Network map unavailable"
          description="A gateway-centered device map will appear once discovery has produced network data."
        />
      )}
    </div>
  );
}
