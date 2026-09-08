import Link from "next/link";
import { Activity } from "lucide-react";
import { EventTimeline } from "@/components/activity/event-timeline";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { getDevices, getEvents } from "@/lib/api";
import type { EventSeverity, EventType } from "@/types/history";

export const metadata = { title: "Activity" };

export const dynamic = "force-dynamic";

const severities = ["info", "low", "medium", "high"] as const;
const eventTypes = [
  "device.discovered",
  "device.online",
  "device.offline",
  "device.updated",
  "device.latency_increased",
  "service.discovered",
  "service.removed",
] as const;

type ActivitySearchParams = {
  device?: string;
  severity?: string;
  type?: string;
  from?: string;
  to?: string;
};

export default async function ActivityPage({
  searchParams,
}: {
  searchParams: Promise<ActivitySearchParams>;
}) {
  const query = await searchParams;
  const deviceId = query.device ? Number(query.device) : undefined;
  const severity = severities.includes(query.severity as EventSeverity)
    ? (query.severity as EventSeverity)
    : undefined;
  const eventType = eventTypes.includes(query.type as EventType)
    ? (query.type as EventType)
    : undefined;
  const [events, devices] = await Promise.all([
    getEvents({
      perPage: 50,
      deviceId: Number.isInteger(deviceId) ? deviceId : undefined,
      severity,
      type: eventType,
      fromTime: query.from,
      toTime: query.to,
    }),
    getDevices({ perPage: 100, sortBy: "name", sortOrder: "asc" }),
  ]);
  const filtered = Boolean(
    deviceId || severity || eventType || query.from || query.to,
  );
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Activity</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Follow device and network changes in chronological order.
        </p>
      </div>
      <form className="border-border bg-card grid gap-3 rounded-lg border p-4 sm:grid-cols-2 xl:grid-cols-6">
        <label className="space-y-1.5 text-xs">
          <span className="text-muted-foreground">Device</span>
          <NativeSelect
            name="device"
            defaultValue={query.device ?? ""}
            className="w-full"
          >
            <option value="">All devices</option>
            {devices.items.map((device) => (
              <option key={device.id} value={device.id}>
                {device.name ?? device.hostname ?? device.ip_address}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="space-y-1.5 text-xs">
          <span className="text-muted-foreground">Event type</span>
          <NativeSelect
            name="type"
            defaultValue={query.type ?? ""}
            className="w-full"
          >
            <option value="">All events</option>
            {eventTypes.map((type) => (
              <option key={type} value={type}>
                {type.replaceAll(".", " ")}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="space-y-1.5 text-xs">
          <span className="text-muted-foreground">Severity</span>
          <NativeSelect
            name="severity"
            defaultValue={query.severity ?? ""}
            className="w-full"
          >
            <option value="">All severities</option>
            {severities.map((severityOption) => (
              <option key={severityOption} value={severityOption}>
                {severityOption.toUpperCase()}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="space-y-1.5 text-xs">
          <span className="text-muted-foreground">From</span>
          <Input type="datetime-local" name="from" defaultValue={query.from} />
        </label>
        <label className="space-y-1.5 text-xs">
          <span className="text-muted-foreground">To</span>
          <Input type="datetime-local" name="to" defaultValue={query.to} />
        </label>
        <div className="flex items-end gap-2">
          <Button type="submit" className="flex-1">
            Apply
          </Button>
          {filtered ? (
            <Button variant="ghost" asChild>
              <Link href="/activity">Clear</Link>
            </Button>
          ) : null}
        </div>
      </form>
      {events.items.length ? (
        <EventTimeline events={events.items} />
      ) : (
        <EmptyState
          icon={Activity}
          title={filtered ? "No matching activity" : "No activity recorded"}
          description={
            filtered
              ? "Adjust or clear the filters to see more events."
              : "Network events will appear here after monitoring starts."
          }
        />
      )}
    </div>
  );
}
