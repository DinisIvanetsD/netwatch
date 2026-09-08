import Link from "next/link";
import {
  Activity,
  BellRing,
  CircleOff,
  MonitorCheck,
  Router,
} from "lucide-react";

import { DeviceTable } from "@/components/devices/device-table";
import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAlerts, getDevices } from "@/lib/api";

export const metadata = { title: "Overview" };
export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const subnet = process.env.NETWATCH_SUBNET ?? "Not configured";
  const [allDevices, onlineDevices, offlineDevices, alerts] = await Promise.all(
    [
      getDevices({ perPage: 5, sortBy: "last_seen", sortOrder: "desc" }),
      getDevices({ perPage: 1, status: "online" }),
      getDevices({ perPage: 1, status: "offline" }),
      getAlerts(),
    ],
  );
  const activeAlerts = alerts.items.filter((alert) => !alert.resolved);
  const availability = allDevices.total
    ? Math.round((onlineDevices.total / allDevices.total) * 100)
    : 0;

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
          <p className="text-foreground mt-1 font-mono text-xs">{subnet}</p>
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
            aria-label="Time range unavailable"
          >
            {["1H", "6H", "24H", "7D"].map((range) => (
              <span
                key={range}
                className={`rounded px-2 py-1 text-[10px] font-medium ${
                  range === "24H"
                    ? "bg-accent text-foreground"
                    : "text-muted-foreground"
                }`}
              >
                {range}
              </span>
            ))}
          </div>
        </CardHeader>
        <CardContent className="flex min-h-72 items-center justify-center pt-5">
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
