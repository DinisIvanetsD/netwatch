import { CircleHelp } from "lucide-react";

import { cn } from "@/lib/utils";

export function InfoTooltip({
  label,
  className,
  showOnParentHover = false,
}: {
  label: string;
  className?: string;
  showOnParentHover?: boolean;
}) {
  return (
    <span className={cn("group relative inline-flex", className)}>
      <button
        type="button"
        className="text-muted-foreground hover:text-foreground focus-visible:text-foreground rounded-full"
        aria-label="Show service explanation"
      >
        <CircleHelp className="size-3.5" aria-hidden="true" />
      </button>
      <span
        role="tooltip"
        className={cn(
          "border-border bg-popover text-popover-foreground pointer-events-none invisible absolute start-1/2 top-full z-50 mt-2 w-72 max-w-[calc(100vw-2rem)] -translate-x-1/2 rounded-lg border p-3 text-xs leading-5 opacity-0 shadow-xl transition-opacity group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100",
          showOnParentHover &&
            "group-hover/service:visible group-hover/service:opacity-100",
        )}
      >
        {label}
      </span>
    </span>
  );
}
