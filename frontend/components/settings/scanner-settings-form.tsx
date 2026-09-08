"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { updateSettings } from "@/lib/api";
import type { NetWatchSettings } from "@/types/settings";

export function ScannerSettingsForm({
  initial,
}: {
  initial: NetWatchSettings;
}) {
  const router = useRouter();
  const [subnet, setSubnet] = useState(initial.subnet);
  const [scanInterval, setScanInterval] = useState(initial.scan_interval);
  const [scanConcurrency, setScanConcurrency] = useState(
    initial.scan_concurrency,
  );
  const [offlineThreshold, setOfflineThreshold] = useState(
    initial.offline_after_missed_scans,
  );
  const [monitoringEnabled, setMonitoringEnabled] = useState(
    initial.monitoring_enabled,
  );
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function save() {
    if (
      !Number.isInteger(scanInterval) ||
      scanInterval < 10 ||
      scanInterval > 86_400 ||
      !Number.isInteger(scanConcurrency) ||
      scanConcurrency < 1 ||
      scanConcurrency > 256 ||
      !Number.isInteger(offlineThreshold) ||
      offlineThreshold < 1 ||
      offlineThreshold > 20
    ) {
      setMessage(
        "Check the interval, concurrency, and offline threshold values.",
      );
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const updated = await updateSettings({
        subnet: subnet.trim(),
        scan_interval: scanInterval,
        scan_concurrency: scanConcurrency,
        offline_after_missed_scans: offlineThreshold,
        monitoring_enabled: monitoringEnabled,
      });
      setSubnet(updated.subnet);
      setMessage("Network and scanner settings saved.");
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Scanner settings could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <label className="flex items-center justify-between gap-4">
        <span>
          <span className="block text-sm font-medium">
            Scheduled monitoring
          </span>
          <span className="text-muted-foreground text-xs">
            Run scans automatically at the configured interval.
          </span>
        </span>
        <input
          type="checkbox"
          checked={monitoringEnabled}
          onChange={(event) => setMonitoringEnabled(event.target.checked)}
          className="accent-primary size-4"
        />
      </label>

      <div>
        <label htmlFor="monitored-subnet" className="text-sm font-medium">
          Monitored subnet
        </label>
        <Input
          id="monitored-subnet"
          value={subnet}
          onChange={(event) => setSubnet(event.target.value)}
          className="mt-2 font-mono"
          spellCheck={false}
          placeholder="192.168.1.0/24"
        />
        <p className="text-muted-foreground mt-2 text-xs">
          RFC 1918 private IPv4 networks only, with a maximum size of /16.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <NumberSetting
          id="scan-interval"
          label="Interval (seconds)"
          value={scanInterval}
          min={10}
          max={86_400}
          onChange={setScanInterval}
        />
        <NumberSetting
          id="scan-concurrency"
          label="Concurrency"
          value={scanConcurrency}
          min={1}
          max={256}
          onChange={setScanConcurrency}
        />
        <NumberSetting
          id="offline-threshold"
          label="Misses before offline"
          value={offlineThreshold}
          min={1}
          max={20}
          onChange={setOfflineThreshold}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={save} disabled={saving}>
          <Save />
          {saving ? "Saving…" : "Save network settings"}
        </Button>
        <p className="text-muted-foreground text-xs" role="status">
          {message}
        </p>
      </div>
    </div>
  );
}

function NumberSetting({
  id,
  label,
  value,
  min,
  max,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <Input
        id={id}
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => {
          const nextValue = event.currentTarget.valueAsNumber;
          if (Number.isFinite(nextValue)) onChange(nextValue);
        }}
        className="mt-2 font-mono"
        required
      />
    </div>
  );
}
