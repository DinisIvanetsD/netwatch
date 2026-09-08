import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  Clock3,
  History,
  Globe2,
  Network,
  Radar,
} from "lucide-react";

import { DeviceStatusBadge } from "@/components/devices/device-status-badge";
import { EventTimeline } from "@/components/activity/event-timeline";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ApiError,
  getDevice,
  getDeviceMetrics,
  getDeviceServices,
  getEvents,
  getInternetActivity,
} from "@/lib/api";
import { formatDate, formatLatency, formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export const metadata = { title: "Device Details" };
export const dynamic = "force-dynamic";

const tabs = [
  "overview",
  "services",
  "internet",
  "activity",
  "history",
] as const;
type DeviceTab = (typeof tabs)[number];

async function loadDevice(id: number) {
  try {
    return await getDevice(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

export default async function DeviceDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const [{ id: rawId }, { tab: rawTab }] = await Promise.all([
    params,
    searchParams,
  ]);
  const deviceId = Number.parseInt(rawId, 10);
  if (!Number.isSafeInteger(deviceId) || deviceId < 1) notFound();

  const device = await loadDevice(deviceId);
  const activeTab: DeviceTab = tabs.includes(rawTab as DeviceTab)
    ? (rawTab as DeviceTab)
    : "overview";
  const displayName = device.name ?? device.hostname ?? device.ip_address;
  const [eventHistory, metricHistory, serviceHistory, internetHistory] =
    await Promise.all([
      activeTab === "activity"
        ? getEvents({ deviceId: device.id, perPage: 50 })
        : null,
      activeTab === "history" ? getDeviceMetrics(device.id, 200) : null,
      activeTab === "services" ? getDeviceServices(device.id) : null,
      activeTab === "internet" ? getInternetActivity(device.id) : null,
    ]);

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ms-2">
        <Link href="/devices">
          <ArrowLeft />
          Back to Devices
        </Link>
      </Button>

      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              {displayName}
            </h1>
            <DeviceStatusBadge status={device.status} />
          </div>
          <div className="text-muted-foreground mt-2 flex flex-wrap gap-x-5 gap-y-1 font-mono text-xs">
            <span>{device.ip_address}</span>
            <span>{device.mac_address ?? "MAC unavailable"}</span>
          </div>
        </div>
        {device.is_gateway ? (
          <div className="border-primary/20 bg-primary/5 text-primary flex items-center gap-2 rounded-lg border px-3 py-2 text-xs">
            <Network className="size-4" aria-hidden="true" />
            Network gateway
          </div>
        ) : null}
      </div>

      <nav
        className="border-border flex gap-1 overflow-x-auto border-b"
        aria-label="Device details"
      >
        {tabs.map((tab) => (
          <Link
            key={tab}
            href={
              tab === "overview"
                ? `/devices/${device.id}`
                : `/devices/${device.id}?tab=${tab}`
            }
            className={cn(
              "border-b-2 px-4 py-2.5 text-sm font-medium capitalize transition-colors",
              activeTab === tab
                ? "border-primary text-foreground"
                : "text-muted-foreground hover:text-foreground border-transparent",
            )}
            aria-current={activeTab === tab ? "page" : undefined}
          >
            {tab}
          </Link>
        ))}
      </nav>

      {activeTab === "overview" ? (
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>Device Information</CardTitle>
            </CardHeader>
            <CardContent className="border-border bg-border grid gap-px overflow-hidden rounded-lg border p-0 sm:grid-cols-2">
              {[
                ["Vendor", device.vendor ?? "Unknown"],
                ["Hostname", device.hostname ?? "Unavailable"],
                ["IP address", device.ip_address],
                ["MAC address", device.mac_address ?? "Unavailable"],
                ["First seen", formatDate(device.first_seen)],
                ["Last seen", formatRelativeTime(device.last_seen)],
              ].map(([label, value]) => (
                <div key={label} className="bg-card p-4">
                  <p className="text-muted-foreground text-[10px] font-semibold tracking-[0.12em] uppercase">
                    {label}
                  </p>
                  <p className="mt-2 text-sm">{value}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Current Health</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="flex items-center gap-3">
                <span className="bg-primary/10 text-primary rounded-lg p-2.5">
                  <Activity className="size-4" aria-hidden="true" />
                </span>
                <div>
                  <p className="text-muted-foreground text-xs">
                    Latest latency
                  </p>
                  <p className="mt-0.5 font-mono text-sm">
                    {formatLatency(device.latency_ms)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="bg-muted text-muted-foreground rounded-lg p-2.5">
                  <Clock3 className="size-4" aria-hidden="true" />
                </span>
                <div>
                  <p className="text-muted-foreground text-xs">
                    Last observation
                  </p>
                  <p className="mt-0.5 text-sm">
                    {formatRelativeTime(device.last_seen)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {activeTab === "services" ? (
        serviceHistory?.items.length ? (
          <Card>
            <CardHeader>
              <CardTitle>Observed services</CardTitle>
            </CardHeader>
            <CardContent className="divide-border divide-y p-0">
              {serviceHistory.items.map((service) => (
                <div
                  key={service.id}
                  className="grid grid-cols-[1fr_auto_auto] gap-4 px-5 py-4 text-sm"
                >
                  <span className="font-medium">{service.service_name}</span>
                  <span className="font-mono">
                    {service.protocol.toUpperCase()} {service.port}
                  </span>
                  <span
                    className={
                      service.active
                        ? "text-emerald-400"
                        : "text-muted-foreground"
                    }
                  >
                    {service.active ? "Active" : "Removed"}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        ) : (
          <EmptyState
            icon={Radar}
            title="No services observed"
            description="Approved TCP service observations for this device will appear after service detection is enabled."
          />
        )
      ) : null}
      {activeTab === "activity" ? (
        eventHistory?.items.length ? (
          <EventTimeline events={eventHistory.items} />
        ) : (
          <EmptyState
            icon={Activity}
            title="No device activity"
            description="State changes and network events associated with this device will appear here."
          />
        )
      ) : null}
      {activeTab === "internet" ? (
        internetHistory?.items.length ? (
          <Card>
            <CardHeader>
              <CardTitle>Internet activity</CardTitle>
            </CardHeader>
            <CardContent className="divide-border divide-y p-0">
              {internetHistory.items.map((item) => (
                <div
                  key={item.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm"
                >
                  <div>
                    <p className="font-mono">{item.domain}</p>
                    <p className="text-muted-foreground mt-1 text-xs capitalize">
                      {item.category} · {formatRelativeTime(item.timestamp)}
                    </p>
                  </div>
                  <span
                    className={
                      item.blocked ? "text-amber-300" : "text-emerald-400"
                    }
                  >
                    {item.blocked ? "Blocked" : "Allowed"}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        ) : (
          <EmptyState
            icon={Globe2}
            title="No DNS activity for this device"
            description="DNS metadata appears here only when a supported provider is configured and the client IP matches this device."
          />
        )
      ) : null}
      {activeTab === "history" ? (
        metricHistory?.items.length ? (
          <Card>
            <CardHeader>
              <CardTitle>Monitoring samples</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-border divide-y">
                {metricHistory.items.map((metric) => (
                  <div
                    key={metric.id}
                    className="grid grid-cols-3 gap-3 px-5 py-3 text-sm"
                  >
                    <time
                      className="text-muted-foreground"
                      dateTime={metric.timestamp}
                    >
                      {formatRelativeTime(metric.timestamp)}
                    </time>
                    <span
                      className={
                        metric.online
                          ? "text-emerald-400"
                          : "text-muted-foreground"
                      }
                    >
                      {metric.online ? "Online" : "Unreachable"}
                    </span>
                    <span className="text-right font-mono">
                      {formatLatency(metric.latency_ms)}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ) : (
          <EmptyState
            icon={History}
            title="No device history"
            description="Availability and latency history will build after scheduled monitoring begins."
          />
        )
      ) : null}
    </div>
  );
}
