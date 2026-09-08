import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardHeader } from "@/components/ui/card";

interface MetricCardProps {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
  tone?: "neutral" | "success" | "warning";
}

const toneClasses = {
  neutral: "bg-primary/10 text-primary",
  success: "bg-emerald-500/10 text-emerald-400",
  warning: "bg-amber-500/10 text-amber-300",
};

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "neutral",
}: MetricCardProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between pb-2">
        <p className="text-muted-foreground text-xs font-semibold tracking-[0.12em]">
          {label}
        </p>
        <span className={`rounded-md p-2 ${toneClasses[tone]}`}>
          <Icon className="size-4" aria-hidden="true" />
        </span>
      </CardHeader>
      <CardContent>
        <p className="font-mono text-3xl font-semibold tracking-tight">
          {value}
        </p>
        <p className="text-muted-foreground mt-1.5 text-xs">{detail}</p>
      </CardContent>
    </Card>
  );
}
