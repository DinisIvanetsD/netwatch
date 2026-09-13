import Link from "next/link";
import {
  Activity,
  Ban,
  BellRing,
  CircleOff,
  MonitorCheck,
  Router,
  ShieldQuestion,
  Users,
} from "lucide-react";

import { DeviceTable } from "@/components/devices/device-table";
import { NetworkActivityChart } from "@/components/charts/network-activity-chart";
import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getAlerts,
  getAccessOverview,
  getBlockedRequests,
  getControlProfiles,
  getDevices,
  getInternetActivitySummary,
  getNetworkActivity,
  getNetworkStatus,
} from "@/lib/api";

export const metadata = { title: "Overview" };
export const dynamic = "force-dynamic";

const ranges = { "1H": 1, "6H": 6, "24H": 24, "7D": 168 } as const;

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string }>;
}) {
  const { range: requestedRange } = await searchParams;
  const range =
    requestedRange && requestedRange in ranges
      ? (requestedRange as keyof typeof ranges)
      : "24H";
  const [
    allDevices,
    onlineDevices,
    offlineDevices,
    alerts,
    activity,
    network,
    access,
    profiles,
    blockedRequests,
    internetSummary,
  ] = await Promise.all([
    getDevices({ perPage: 5, sortBy: "last_seen", sortOrder: "desc" }),
    getDevices({ perPage: 1, status: "online" }),
    getDevices({ perPage: 1, status: "offline" }),
    getAlerts(),
    getNetworkActivity(ranges[range]),
    getNetworkStatus(),
    getAccessOverview(),
    getControlProfiles(),
    getBlockedRequests({ hours: 24, perPage: 1 }),
    getInternetActivitySummary(undefined, 24),
  ]);
  const activeAlerts = alerts.items.filter((alert) => !alert.resolved);
  const availability = allDevices.total
    ? Math.round((onlineDevices.total / allDevices.total) * 100)
    : 0;
  const childProfile = profiles.items.find(
    (profile) => profile.name.toLowerCase() === "child",
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Network Overview
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Monitor devices, services and activity across your network.
          </p>
        </div>
        <div className="text-sm md:text-end">
          <p className="text-muted-foreground">Network</p>
          <p className="text-foreground mt-1 font-mono text-xs">
            {network.subnet}
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="TOTAL DEVICES"
          value={String(allDevices.total)}
          detail={allDevices.total ? "Known inventory" : "No scan data yet"}
          icon={Router}
        />
        <MetricCard
          label="ONLINE"
          value={String(onlineDevices.total)}
          detail={
            allDevices.total
              ? `${availability}% availability`
              : "Availability unavailable"
          }
          icon={MonitorCheck}
          tone="success"
        />
        <MetricCard
          label="OFFLINE"
          value={String(offlineDevices.total)}
          detail={
            offlineDevices.total
              ? "Currently unreachable"
              : "No offline devices"
          }
          icon={CircleOff}
          tone="neutral"
        />
        <MetricCard
          label="ACTIVE ALERTS"
          value={String(activeAlerts.length)}
          detail={
            activeAlerts.some((alert) => alert.severity === "high")
              ? "High severity needs review"
              : activeAlerts.length
                ? "Unresolved alerts"
                : "No unresolved alerts"
          }
          icon={BellRing}
          tone="warning"
        />
      </div>

      <div>
        <div className="mb-3 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold">Home Network Control</h2>
            <p className="text-muted-foreground mt-1 text-xs">
              Identity, parental policy, and DNS-filtering status.
            </p>
          </div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/access-control">Review access</Link>
          </Button>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="UNKNOWN DEVICES"
            value={String(access.unknown)}
            detail={
              access.unknown
                ? "Needs administrator review"
                : "Inventory reviewed"
            }
            icon={ShieldQuestion}
            tone={access.unknown ? "warning" : "neutral"}
          />
          <MetricCard
            label="CHILD DEVICES"
            value={String(childProfile?.device_count ?? 0)}
            detail={
              childProfile
                ? "Assigned to Child profile"
                : "Child profile not configured"
            }
            icon={Users}
          />
          <MetricCard
            label="BLOCKED TODAY"
            value={String(blockedRequests.total)}
            detail="DNS provider observations"
            icon={Ban}
            tone="warning"
          />
          <MetricCard
            label="INFERRED SERVICES"
            value={String(internetSummary.top_services.length)}
            detail={
              internetSummary.top_services[0]
                ? `Top: ${internetSummary.top_services[0].service}`
                : "No DNS activity yet"
            }
            icon={Activity}
          />
        </div>
      </div>

      <Card>
        <CardHeader className="border-border flex-row items-center justify-between border-b">
          <div>
            <CardTitle>Network Activity</CardTitle>
            <p className="text-muted-foreground mt-1 text-xs">
              Historical metrics appear after monitoring begins.
            </p>
          </div>
          <div
            className="border-border bg-muted/30 flex rounded-md border p-0.5"
            role="group"
            aria-label="Network activity time range"
          >
            {Object.keys(ranges).map((option) => (
              <Link
                key={option}
                href={`/dashboard?range=${option}`}
                className={`rounded px-2 py-1 text-[10px] font-medium ${
                  option === range
                    ? "bg-accent text-foreground"
                    : "text-muted-foreground"
                }`}
                aria-current={option === range ? "page" : undefined}
              >
                {option}
              </Link>
            ))}
          </div>
        </CardHeader>
        <CardContent className="flex min-h-72 items-center justify-center pt-5">
          {activity.points.length ? (
            <NetworkActivityChart points={activity.points} />
          ) : (
            <div className="text-center">
              <Activity
                className="text-muted-foreground mx-auto size-6"
                aria-hidden="true"
              />
              <p className="mt-3 text-sm font-medium">No activity recorded</p>
              <p className="text-muted-foreground mt-1 text-xs">
                Run a network scan to begin collecting metrics.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <div>
        <div className="mb-3 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold">Devices</h2>
            <p className="text-muted-foreground mt-1 text-xs">
              Recently observed network hosts.
            </p>
          </div>
          {allDevices.total ? (
            <Button variant="ghost" size="sm" asChild>
              <Link href="/devices">View all</Link>
            </Button>
          ) : null}
        </div>
        <DeviceTable
          devices={allDevices.items}
          sortBy="last_seen"
          sortOrder="desc"
          query={{}}
          filtered={false}
        />
      </div>
    </div>
  );
}
