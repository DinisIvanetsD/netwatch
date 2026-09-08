import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { DeviceTrustState, InternetAccessState } from "@/types/device";

const trustStyles: Record<DeviceTrustState, string> = {
  trusted: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  unknown: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  quarantined: "border-orange-500/25 bg-orange-500/10 text-orange-300",
  blocked: "border-red-500/25 bg-red-500/10 text-red-300",
  ignored: "border-border bg-secondary text-muted-foreground",
};

export function TrustBadge({ state }: { state: DeviceTrustState }) {
  return (
    <Badge variant="secondary" className={cn("capitalize", trustStyles[state])}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {state}
    </Badge>
  );
}

export function InternetAccessBadge({ state }: { state: InternetAccessState }) {
  const variant =
    state === "allowed"
      ? "success"
      : state === "paused"
        ? "warning"
        : "secondary";
  return (
    <Badge
      variant={variant}
      className={cn(
        state === "blocked" && "border-red-500/25 bg-red-500/10 text-red-300",
      )}
    >
      {state === "allowed"
        ? "Internet allowed"
        : state === "paused"
          ? "Internet paused"
          : "Internet blocked"}
    </Badge>
  );
}

export function EnforcementBadge({ status }: { status: string }) {
  const variant =
    status === "active"
      ? "success"
      : status === "error"
        ? "warning"
        : "secondary";
  return <Badge variant={variant}>{status.replaceAll("_", " ")}</Badge>;
}
