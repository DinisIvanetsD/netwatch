import Link from "next/link";
import { Activity, ArrowDown, ArrowUp, Gauge, Radar } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { EventType, NetworkEvent } from "@/types/history";

const icons = {
  "device.discovered": Radar,
  "device.online": ArrowUp,
  "device.offline": ArrowDown,
  "device.updated": Activity,
  "device.latency_increased": Gauge,
  "service.discovered": Radar,
  "service.removed": Radar,
} satisfies Record<EventType, typeof Activity>;

const severityStyles = {
  info: "border-blue-500/20 bg-blue-500/10 text-blue-300",
  low: "border-cyan-500/20 bg-cyan-500/10 text-cyan-300",
  medium: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  high: "border-red-500/20 bg-red-500/10 text-red-300",
};

export function EventTimeline({ events }: { events: NetworkEvent[] }) {
  return (
    <Card>
      <CardContent className="p-0">
        <ol className="divide-border divide-y">
          {events.map((event) => {
            const Icon = icons[event.type];
            return (
              <li key={event.id} className="flex gap-4 p-4 sm:p-5">
                <span className="bg-muted text-muted-foreground mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg">
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">{event.message}</p>
                    <Badge
                      variant="secondary"
                      className={cn(
                        "text-[10px] uppercase",
                        severityStyles[event.severity],
                      )}
                    >
                      {event.severity}
                    </Badge>
                  </div>
                  <div className="text-muted-foreground mt-1 flex flex-wrap gap-x-3 text-xs">
                    {event.device_id && event.device_name ? (
                      <Link
                        href={`/devices/${event.device_id}?tab=activity`}
                        className="hover:text-foreground transition-colors"
                      >
                        {event.device_name}
                      </Link>
                    ) : null}
                    <time
                      dateTime={event.timestamp}
                      title={new Date(event.timestamp).toLocaleString()}
                    >
                      {formatRelativeTime(event.timestamp)}
                    </time>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}
