import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
}: EmptyStateProps) {
  return (
    <Card>
      <CardContent className="flex min-h-56 flex-col items-center justify-center px-6 py-12 text-center">
        <span className="border-border bg-muted/50 text-muted-foreground mb-4 rounded-xl border p-3">
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="text-muted-foreground mt-2 max-w-md text-sm leading-6">
          {description}
        </p>
      </CardContent>
    </Card>
  );
}
