"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { updateAlertSettings } from "@/lib/api";
import type { NetWatchSettings } from "@/types/settings";

const rules = [
  ["new_device_alerts", "New device alerts"],
  ["device_offline_alerts", "Device offline alerts"],
  ["new_service_alerts", "New service alerts"],
  ["latency_alerts", "Latency alerts"],
] as const;
export function AlertSettingsForm({ initial }: { initial: NetWatchSettings }) {
  const [values, setValues] = useState(
    () =>
      Object.fromEntries(rules.map(([key]) => [key, initial[key]])) as Record<
        (typeof rules)[number][0],
        boolean
      >,
  );
  const [message, setMessage] = useState("");
  async function save() {
    await updateAlertSettings(values);
    setMessage("Alert rules saved.");
  }
  return (
    <div className="space-y-4">
      {rules.map(([key, label]) => (
        <label key={key} className="flex items-center justify-between text-sm">
          <span>{label}</span>
          <input
            type="checkbox"
            className="accent-primary size-4"
            checked={values[key]}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                [key]: event.target.checked,
              }))
            }
          />
        </label>
      ))}
      <div className="flex items-center gap-3">
        <Button onClick={save}>Save alert rules</Button>
        <span role="status" className="text-muted-foreground text-xs">
          {message}
        </span>
      </div>
    </div>
  );
}
