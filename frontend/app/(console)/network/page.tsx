import Link from "next/link";
import { Activity, Network, Router, ServerCog } from "lucide-react";
import { DeviceStatusBadge } from "@/components/devices/device-status-badge";
import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  getDevices,
  getNetworkProfiles,
  getNetworkStatus,
  getProviderCapabilities,
} from "@/lib/api";
import {
  deviceDisplayName,
  formatLatency,
  formatRelativeTime,
  hasAssignedDeviceName,
} from "@/lib/format";

export const metadata = { title: "Network" };

export const dynamic = "force-dynamic";

export default async function NetworkPage() {
  const [network, devices, providers, profiles] = await Promise.all([
    getNetworkStatus(),
    getDevices({ perPage: 100, sortBy: "ip_address", sortOrder: "asc" }),
    getProviderCapabilities(),
    getNetworkProfiles(),
  ]);
  const gateway = devices.items.find((device) => device.is_gateway);
  const peers = devices.items.filter((device) => !device.is_gateway);
  const networkProvider = providers.items.find(
    (provider) => provider.kind === "network",
  );
  const routerControlled = Boolean(
    networkProvider?.capabilities.quarantine_device ||
    networkProvider?.capabilities.firewall_rules,
  );
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Network</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Verified LAN scope, monitoring health, and discovered devices.
        </p>
      </div>
      {network.discovery_mode === "windows_sensor" ? (
        <div className="border-primary/20 bg-primary/5 flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3">
          <div>
            <p className="text-sm font-medium">Windows network sensor active</p>
            <p className="text-muted-foreground mt-1 text-xs">
              NetWatch is reading the physical{" "}
              {network.interface_name ?? "network"}
              {network.local_ip
                ? ` interface at ${network.local_ip}`
                : " interface"}
              .
            </p>
          </div>
          <p className="text-primary text-xs font-medium">
            {network.auto_detect_network
              ? "Automatic network switching on"
              : "Manual subnet mode"}
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 px-4 py-3">
          <p className="text-sm font-medium">Container-only discovery</p>
          <p className="text-muted-foreground mt-1 text-xs">
            Start the optional Windows sensor for physical-interface MAC
            addresses, gateway facts, and automatic switching when this PC
            changes network.
          </p>
        </div>
      )}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Network profiles</CardTitle>
              <p className="text-muted-foreground mt-1 text-xs leading-5">
                Inventories stay separated when this computer moves between
                Wi-Fi, hotspots, or physical LANs.
              </p>
            </div>
            <Badge variant="secondary">
              {profiles.items.length} context
              {profiles.items.length === 1 ? "" : "s"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {profiles.items.map((profile) => (
            <div
              key={`${profile.subnet}-${profile.network_id}`}
              className={
                profile.is_current
                  ? "border-primary/30 bg-primary/5 rounded-lg border p-3"
                  : "border-border bg-muted/20 rounded-lg border p-3"
              }
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">{profile.label}</p>
                  <p className="text-muted-foreground mt-1 font-mono text-xs">
                    {profile.subnet}
                  </p>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  {profile.is_current ? (
                    <Badge variant="success">Active</Badge>
                  ) : null}
                  <span className="text-muted-foreground">
                    {profile.devices_known} device
                    {profile.devices_known === 1 ? "" : "s"}
                  </span>
                  <span className="text-muted-foreground">
                    {profile.scan_count} scan
                    {profile.scan_count === 1 ? "" : "s"}
                  </span>
                </div>
              </div>
              <p className="text-muted-foreground mt-2 text-xs">
                {profile.is_current
                  ? "Only devices discovered in this active context are shown below."
                  : "Kept as history; it is not mixed into the current device inventory."}
              </p>
            </div>
          ))}
        </CardContent>
      </Card>
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
      <Card>
        <CardHeader className="border-border border-b">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Router control</CardTitle>
              <p className="text-muted-foreground mt-1 text-xs">
                Gateway detection does not grant administrative access.
              </p>
            </div>
            <Badge variant={routerControlled ? "success" : "secondary"}>
              {routerControlled ? "Automated" : "Manual / unavailable"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 pt-5 md:grid-cols-[1fr_auto] md:items-center">
          <div>
            <p className="text-sm font-semibold">
              {gateway ? deviceDisplayName(gateway) : "Detected gateway"}
            </p>
            <p className="text-muted-foreground mt-1 text-xs leading-5">
              {routerControlled
                ? `${networkProvider?.display_name} can apply verified router/firewall controls.`
                : networkProvider?.provider_id === "technitium_dns_containment"
                  ? "Technitium can apply DNS-only Internet containment. This CHITA/NOS gateway still requires its Device Filter or a supported router API for full quarantine."
                  : "This router has no configured supported control API. CHITA/NOS devices can be managed manually with Device Filter; OpenWrt or OPNsense can provide automatable firewall control."}
            </p>
          </div>
          {network.gateway ? (
            <a
              href={`http://${network.gateway}`}
              target="_blank"
              rel="noreferrer"
              className="border-border hover:border-primary/40 rounded-lg border px-4 py-2 text-center text-sm font-medium transition-colors"
            >
              Open router admin
            </a>
          ) : null}
        </CardContent>
      </Card>
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
                {gateway ? deviceDisplayName(gateway) : "Gateway"}
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
                  href={`/devices/${device.id}${hasAssignedDeviceName(device) ? "" : "?tab=access"}`}
                  className="border-border hover:border-primary/30 bg-muted/20 rounded-lg border p-4 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">
                      {deviceDisplayName(device)}
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
