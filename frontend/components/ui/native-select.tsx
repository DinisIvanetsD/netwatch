import * as React from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

function NativeSelect({
  className,
  children,
  ...props
}: React.ComponentProps<"select">) {
  return (
    <span className="relative inline-flex">
      <select
        data-slot="native-select"
        className={cn(
          "border-input bg-background text-foreground focus-visible:ring-ring h-9 appearance-none rounded-md border py-1 ps-3 pe-8 text-sm transition-colors outline-none focus-visible:ring-2",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown className="text-muted-foreground pointer-events-none absolute end-2.5 top-1/2 size-3.5 -translate-y-1/2" />
    </span>
  );
}

export { NativeSelect };
