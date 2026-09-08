import { Activity } from "lucide-react";
import { EventTimeline } from "@/components/activity/event-timeline";
import { EmptyState } from "@/components/empty-state";
import { getEvents } from "@/lib/api";

export const metadata = { title: "Activity" };

export const dynamic = "force-dynamic";

export default async function ActivityPage() {
  const events = await getEvents({ perPage: 50 });
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Activity</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Follow device and network changes in chronological order.
        </p>
      </div>
      {events.items.length ? (
        <EventTimeline events={events.items} />
      ) : (
        <EmptyState
          icon={Activity}
          title="No activity recorded"
          description="Network events will appear here after monitoring starts."
        />
      )}
    </div>
  );
}
