import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { DeviceStatus } from "@/types/device";

const statusStyles: Record<DeviceStatus, string> = {
  online: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  offline: "border-border bg-muted/60 text-muted-foreground",
  new: "border-sky-500/25 bg-sky-500/10 text-sky-300",
  unknown: "border-amber-500/25 bg-amber-500/10 text-amber-300",
};

const dotStyles: Record<DeviceStatus, string> = {
  online: "bg-emerald-400",
  offline: "bg-muted-foreground",
  new: "bg-sky-300",
  unknown: "bg-amber-300",
};

export function DeviceStatusBadge({ status }: { status: DeviceStatus }) {
  return (
    <Badge
      variant="secondary"
      className={statusStyles[status]}
      aria-label={`Device status: ${status}`}
    >
      <span
        className={cn("size-1.5 rounded-full", dotStyles[status])}
        aria-hidden="true"
      />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}
