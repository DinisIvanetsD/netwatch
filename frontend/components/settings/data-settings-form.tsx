"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Database, Trash2 } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { clearHistory, updateSettings } from "@/lib/api";
import type { NetWatchSettings } from "@/types/settings";

const retentionOptions = [7, 30, 90, 180, 365];

export function DataSettingsForm({ initial }: { initial: NetWatchSettings }) {
  const router = useRouter();
  const [retentionDays, setRetentionDays] = useState(initial.retention_days);
  const [saving, setSaving] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [message, setMessage] = useState("");
  const choices = retentionOptions.includes(initial.retention_days)
    ? retentionOptions
    : [initial.retention_days, ...retentionOptions].toSorted((a, b) => a - b);

  async function saveRetention() {
    setSaving(true);
    setMessage("");
    try {
      await updateSettings({ retention_days: retentionDays });
      setMessage("Retention period saved.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Retention could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function removeHistory() {
    setClearing(true);
    setMessage("");
    try {
      const result = await clearHistory();
      const total =
        result.metrics_deleted +
        result.events_deleted +
        result.alerts_deleted +
        result.scans_deleted +
        result.internet_activity_deleted;
      setMessage(
        `${total} historical records removed. Devices and services were kept.`,
      );
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "History could not be cleared.",
      );
    } finally {
      setClearing(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <label htmlFor="retention-days" className="text-sm font-medium">
          Retention period
        </label>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <NativeSelect
            id="retention-days"
            value={retentionDays}
            onChange={(event) => setRetentionDays(Number(event.target.value))}
          >
            {choices.map((days) => (
              <option key={days} value={days}>
                {days} days
              </option>
            ))}
          </NativeSelect>
          <Button variant="outline" onClick={saveRetention} disabled={saving}>
            <Database />
            {saving ? "Saving…" : "Save retention"}
          </Button>
        </div>
        <p className="text-muted-foreground mt-2 text-xs">
          Expired metrics, events, alerts, DNS activity, and scan records are
          pruned after scans.
        </p>
      </div>

      <div className="border-border border-t pt-5">
        <p className="text-sm font-medium">Clear historical data</p>
        <p className="text-muted-foreground mt-1 text-xs leading-5">
          Removes metrics, events, alerts, DNS activity, and completed scan
          records. Device inventory and currently detected services remain
          available.
        </p>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive" className="mt-3" disabled={clearing}>
              <Trash2 />
              {clearing ? "Clearing…" : "Clear historical data"}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Clear all historical data?</AlertDialogTitle>
              <AlertDialogDescription>
                This cannot be undone. Device inventory and active service
                observations will not be deleted.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={removeHistory}>
                Clear history
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      <p className="text-muted-foreground text-xs" role="status">
        {message}
      </p>
    </div>
  );
}
