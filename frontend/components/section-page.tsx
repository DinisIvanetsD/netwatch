import type { LucideIcon } from "lucide-react";

import { EmptyState } from "@/components/empty-state";

interface SectionPageProps {
  title: string;
  description: string;
  emptyTitle: string;
  emptyDescription: string;
  icon: LucideIcon;
}

export function SectionPage({
  title,
  description,
  emptyTitle,
  emptyDescription,
  icon,
}: SectionPageProps) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-muted-foreground mt-1 text-sm">{description}</p>
      </div>
      <EmptyState
        icon={icon}
        title={emptyTitle}
        description={emptyDescription}
      />
    </div>
  );
}
