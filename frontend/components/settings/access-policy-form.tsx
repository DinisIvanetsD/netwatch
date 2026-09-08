"use client";

import { useState } from "react";
import { Save, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { updateSettings } from "@/lib/api";
import type { NetWatchSettings } from "@/types/settings";

export function AccessPolicyForm({
  initial,
  routerControlAvailable,
}: {
  initial: NetWatchSettings;
  routerControlAvailable: boolean;
}) {
  const [policy, setPolicy] = useState(initial.new_device_policy);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const requestsControl =
    policy === "quarantine_alert" || policy === "block_alert";

  async function save() {
    setSaving(true);
    setMessage("");
    try {
      const updated = await updateSettings({ new_device_policy: policy });
      setPolicy(updated.new_device_policy);
      setMessage("New-device policy saved.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Policy could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="new-device-policy" className="text-sm font-medium">
          New device policy
        </label>
        <NativeSelect
          id="new-device-policy"
          value={policy}
          onChange={(event) =>
            setPolicy(
              event.target.value as NetWatchSettings["new_device_policy"],
            )
          }
          className="mt-2 w-full"
        >
          <option value="allow">Allow automatically</option>
          <option value="allow_alert">Allow + alert (recommended)</option>
          <option value="quarantine_alert">Quarantine + alert</option>
          <option value="block_alert">Block + alert</option>
        </NativeSelect>
      </div>
      <p className="text-muted-foreground text-xs leading-5">
        The default permits legitimate devices and asks you to review them.
        Manual trust decisions persist across later scans.
      </p>
      {requestsControl && !routerControlAvailable ? (
        <div className="flex gap-3 rounded-lg border border-amber-500/25 bg-amber-500/5 p-3 text-xs leading-5">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-amber-300" />
          <p>
            This policy will still create an alert, but automatic network
            enforcement cannot run until a compatible router provider is
            configured.
          </p>
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={save} disabled={saving}>
          <Save />
          {saving ? "Saving…" : "Save access policy"}
        </Button>
        <p className="text-muted-foreground text-xs" role="status">
          {message}
        </p>
      </div>
    </div>
  );
}
