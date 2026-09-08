"use client";

import { useState } from "react";
import { Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { updateServiceSettings } from "@/lib/api";
import type { NetWatchSettings } from "@/types/settings";

export function ServiceSettingsForm({
  initial,
}: {
  initial: NetWatchSettings;
}) {
  const [enabled, setEnabled] = useState(initial.service_scan_enabled);
  const [ports, setPorts] = useState(initial.service_ports.join(", "));
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  async function save() {
    const parsed = ports.split(",").map((port) => Number(port.trim()));
    if (
      !parsed.length ||
      parsed.some((port) => !Number.isInteger(port) || port < 1 || port > 65535)
    ) {
      setMessage("Enter valid ports from 1 to 65535, separated by commas.");
      return;
    }
    setSaving(true);
    try {
      const updated = await updateServiceSettings({
        service_scan_enabled: enabled,
        service_ports: parsed,
      });
      setPorts(updated.service_ports.join(", "));
      setMessage("Scanner settings saved.");
    } catch {
      setMessage(
        "Settings could not be saved. Check that the API is available.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <label className="flex items-center justify-between gap-4">
        <span>
          <span className="block text-sm font-medium">Service detection</span>
          <span className="text-muted-foreground text-xs">
            Check approved TCP ports after discovery.
          </span>
        </span>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
          className="accent-primary size-4"
        />
      </label>
      <div>
        <label htmlFor="service-ports" className="text-sm font-medium">
          Approved TCP ports
        </label>
        <Input
          id="service-ports"
          value={ports}
          onChange={(event) => setPorts(event.target.value)}
          className="mt-2 font-mono"
        />
        <p className="text-muted-foreground mt-2 text-xs">
          Up to 64 ports. NetWatch performs connection checks only.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={saving}>
          <Save />
          {saving ? "Saving…" : "Save scanner settings"}
        </Button>
        <p className="text-muted-foreground text-xs" role="status">
          {message}
        </p>
      </div>
    </div>
  );
}
