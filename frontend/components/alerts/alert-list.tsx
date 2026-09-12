"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Check, Eye, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { updateAlert } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import type { Alert } from "@/types/alert";

const PAGE_SIZE = 20;

export function AlertList({ initial }: { initial: Alert[] }) {
  const [alerts, setAlerts] = useState(initial);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [device, setDevice] = useState("");
  const [unresolvedOnly, setUnresolvedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [workingId, setWorkingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<"success" | "error">("error");

  const devices = useMemo(
    () =>
      Array.from(
        new Map(
          alerts.flatMap((alert) =>
            alert.device_id && alert.device_name
              ? [[String(alert.device_id), alert.device_name] as const]
              : [],
          ),
        ),
      ).toSorted(([, first], [, second]) => first.localeCompare(second)),
    [alerts],
  );
  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase();
    return alerts.filter((alert) => {
      if (severity && alert.severity !== severity) return false;
      if (device && String(alert.device_id) !== device) return false;
      if (unresolvedOnly && alert.resolved) return false;
      if (!term) return true;
      return [
        alert.title,
        alert.description,
        alert.device_name,
        alert.type,
      ].some((value) => value?.toLocaleLowerCase().includes(term));
    });
  }, [alerts, device, search, severity, unresolvedOnly]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visible = filtered.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );

  function resetPage() {
    setPage(1);
  }

  async function change(
    id: number,
    payload: { read?: boolean; resolved?: boolean },
  ) {
    setWorkingId(id);
    setMessage("");
    try {
      const updated = await updateAlert(id, payload);
      setAlerts((current) =>
        current.map((alert) => (alert.id === id ? updated : alert)),
      );
      setMessageKind("success");
      setMessage(
        updated.resolved ? "Alert resolved." : "Alert marked as read.",
      );
    } catch (error) {
      setMessageKind("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "The alert could not be updated.",
      );
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="border-border bg-card grid gap-3 rounded-lg border p-4 md:grid-cols-2 xl:grid-cols-[minmax(16rem,1fr)_12rem_14rem_auto]">
        <label className="relative">
          <span className="sr-only">Search alerts</span>
          <Search
            className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
            aria-hidden="true"
          />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              resetPage();
            }}
            placeholder="Search alerts or devices"
            className="pl-9"
          />
        </label>
        <label>
          <span className="sr-only">Filter by severity</span>
          <NativeSelect
            value={severity}
            onChange={(event) => {
              setSeverity(event.target.value);
              resetPage();
            }}
            className="w-full"
          >
            <option value="">All severities</option>
            <option value="info">INFO</option>
            <option value="low">LOW</option>
            <option value="medium">MEDIUM</option>
            <option value="high">HIGH</option>
          </NativeSelect>
        </label>
        <label>
          <span className="sr-only">Filter by device</span>
          <NativeSelect
            value={device}
            onChange={(event) => {
              setDevice(event.target.value);
              resetPage();
            }}
            className="w-full"
          >
            <option value="">All devices</option>
            {devices.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="border-border flex min-h-9 items-center gap-2 rounded-md border px-3 text-sm">
          <input
            type="checkbox"
            checked={unresolvedOnly}
            onChange={(event) => {
              setUnresolvedOnly(event.target.checked);
              resetPage();
            }}
            className="accent-primary size-4"
          />
          Unresolved only
        </label>
      </div>

      <div className="text-muted-foreground flex items-center justify-between text-xs">
        <span>
          Showing {visible.length} of {filtered.length} matching alerts
        </span>
        <span className="flex gap-3" aria-label="Alert summary">
          <span>{alerts.filter((alert) => !alert.read).length} unread</span>
          <span>
            {alerts.filter((alert) => !alert.resolved).length} unresolved
          </span>
        </span>
        {pageCount > 1 ? (
          <span>
            Page {currentPage} of {pageCount}
          </span>
        ) : null}
      </div>

      {visible.length ? (
        <Card>
          <CardContent className="divide-border divide-y p-0">
            {visible.map((alert) => (
              <div
                key={alert.id}
                className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant={
                        alert.severity === "high" ? "warning" : "secondary"
                      }
                    >
                      {alert.severity.toUpperCase()}
                    </Badge>
                    <Badge variant={alert.resolved ? "success" : "default"}>
                      {alert.resolved ? "Resolved" : "Open"}
                    </Badge>
                    <Badge variant={alert.read ? "secondary" : "warning"}>
                      {alert.read ? "READ" : "UNREAD"}
                    </Badge>
                    <h2 className="text-sm font-semibold">{alert.title}</h2>
                  </div>
                  <div className="border-border bg-muted/30 mt-3 rounded-md border px-3 py-2">
                    <p className="text-muted-foreground text-[10px] font-semibold tracking-wide uppercase">
                      Incident evidence
                    </p>
                    <p className="text-muted-foreground mt-1 text-sm">
                      {alert.description}
                    </p>
                    <p className="text-muted-foreground mt-1 text-xs">
                      Signal: {alert.type}
                    </p>
                  </div>
                  <div className="text-muted-foreground mt-1 flex gap-3 text-xs">
                    {alert.device_id && alert.device_name ? (
                      <Link
                        href={`/devices/${alert.device_id}?tab=activity`}
                        className="text-primary hover:underline"
                      >
                        {alert.device_name}
                      </Link>
                    ) : null}
                    <span>
                      {alert.resolved ? "Resolved" : "Open"} ·{" "}
                      {alert.read ? "Read" : "Unread"}
                    </span>
                    <time dateTime={alert.created_at} suppressHydrationWarning>
                      {formatRelativeTime(alert.created_at)}
                    </time>
                  </div>
                </div>
                <div className="flex gap-2">
                  {!alert.read ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={workingId === alert.id}
                      onClick={() => change(alert.id, { read: true })}
                    >
                      <Eye />
                      Mark read
                    </Button>
                  ) : null}
                  {!alert.resolved ? (
                    <Button
                      size="sm"
                      disabled={workingId === alert.id}
                      onClick={() =>
                        change(alert.id, { resolved: true, read: true })
                      }
                    >
                      <Check />
                      {workingId === alert.id ? "Updating…" : "Resolve"}
                    </Button>
                  ) : null}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : (
        <div className="border-border bg-card rounded-lg border px-6 py-12 text-center">
          <p className="text-sm font-medium">No matching alerts</p>
          <p className="text-muted-foreground mt-1 text-xs">
            Adjust the filters or search terms to see more results.
          </p>
        </div>
      )}

      {pageCount > 1 ? (
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage === 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage === pageCount}
            onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
          >
            Next
          </Button>
        </div>
      ) : null}

      <p
        className={
          messageKind === "error"
            ? "text-destructive text-xs"
            : "text-xs text-emerald-400"
        }
        role="status"
        aria-live="polite"
      >
        {message}
      </p>
    </div>
  );
}
