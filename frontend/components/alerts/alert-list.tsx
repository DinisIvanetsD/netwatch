"use client";
import { useState } from "react";
import Link from "next/link";
import { Check, Eye } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { updateAlert } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import type { Alert } from "@/types/alert";

export function AlertList({ initial }: { initial: Alert[] }) {
  const [alerts, setAlerts] = useState(initial);
  async function change(
    id: number,
    payload: { read?: boolean; resolved?: boolean },
  ) {
    const updated = await updateAlert(id, payload);
    setAlerts((current) =>
      current.map((alert) => (alert.id === id ? updated : alert)),
    );
  }
  return (
    <Card>
      <CardContent className="divide-border divide-y p-0">
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center"
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant={
                    alert.severity === "medium" || alert.severity === "high"
                      ? "warning"
                      : "secondary"
                  }
                >
                  {alert.severity.toUpperCase()}
                </Badge>
                <h2 className="text-sm font-semibold">{alert.title}</h2>
                {alert.resolved ? (
                  <span className="text-muted-foreground text-xs">
                    Resolved
                  </span>
                ) : null}
              </div>
              <p className="text-muted-foreground mt-1 text-sm">
                {alert.description}
              </p>
              <div className="text-muted-foreground mt-1 flex gap-3 text-xs">
                {alert.device_id && alert.device_name ? (
                  <Link href={`/devices/${alert.device_id}`}>
                    {alert.device_name}
                  </Link>
                ) : null}
                <time dateTime={alert.created_at}>
                  {formatRelativeTime(alert.created_at)}
                </time>
              </div>
            </div>
            <div className="flex gap-2">
              {!alert.read ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => change(alert.id, { read: true })}
                >
                  <Eye />
                  Mark read
                </Button>
              ) : null}
              {!alert.resolved ? (
                <Button
                  size="sm"
                  onClick={() =>
                    change(alert.id, { resolved: true, read: true })
                  }
                >
                  <Check />
                  Resolve
                </Button>
              ) : null}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
