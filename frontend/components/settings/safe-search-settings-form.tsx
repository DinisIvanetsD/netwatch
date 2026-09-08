"use client";

import { useState } from "react";
import { Save, SearchCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { updateSafeSearch } from "@/lib/api";
import type { SafeSearchConfiguration } from "@/types/integration";

const services: Array<[keyof SafeSearchConfiguration, string]> = [
  ["google", "Google"],
  ["bing", "Bing"],
  ["youtube", "YouTube"],
  ["duckduckgo", "DuckDuckGo"],
  ["ecosia", "Ecosia"],
  ["pixabay", "Pixabay"],
  ["yandex", "Yandex"],
];

export function SafeSearchSettingsForm({
  initial,
  available,
  providerName,
}: {
  initial: SafeSearchConfiguration | null;
  available: boolean;
  providerName: string;
}) {
  const [value, setValue] = useState<SafeSearchConfiguration>(
    initial ?? {
      enabled: false,
      google: true,
      bing: true,
      youtube: true,
      duckduckgo: true,
      ecosia: true,
      pixabay: true,
      yandex: true,
    },
  );
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(
    available && !initial
      ? "Safe Search settings could not be read from the provider."
      : "",
  );

  async function save() {
    setSaving(true);
    setMessage("");
    try {
      const updated = await updateSafeSearch(value);
      setValue(updated);
      setMessage("Safe Search settings confirmed by the DNS provider.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Safe Search could not be updated.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!available) {
    return (
      <div className="flex items-start gap-3">
        <SearchCheck className="text-muted-foreground mt-0.5 size-4" />
        <div>
          <p className="text-sm font-medium">Provider support required</p>
          <p className="text-muted-foreground mt-1 text-xs leading-5">
            {providerName} does not currently expose Safe Search controls. No
            enforcement is being claimed.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium">Global DNS Safe Search</p>
          <p className="text-muted-foreground mt-1 text-xs leading-5">
            Enforced by {providerName} for clients using it as DNS. This is a
            provider-wide setting, not traffic interception.
          </p>
        </div>
        <Badge variant={value.enabled ? "success" : "secondary"}>
          {value.enabled ? "Enabled" : "Disabled"}
        </Badge>
      </div>
      <label className="border-border flex items-center justify-between rounded-lg border p-3 text-sm font-medium">
        Enable Safe Search
        <input
          type="checkbox"
          checked={value.enabled}
          onChange={(event) =>
            setValue({ ...value, enabled: event.target.checked })
          }
          className="accent-primary size-4"
        />
      </label>
      <div className="grid gap-2 sm:grid-cols-2">
        {services.map(([key, label]) => (
          <label
            key={key}
            className="border-border flex items-center justify-between rounded-lg border p-3 text-sm"
          >
            {label}
            <input
              type="checkbox"
              checked={value[key]}
              disabled={!value.enabled}
              onChange={(event) =>
                setValue({ ...value, [key]: event.target.checked })
              }
              className="accent-primary size-4"
            />
          </label>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={save} disabled={saving}>
          <Save />
          {saving ? "Saving…" : "Save Safe Search"}
        </Button>
        <p className="text-muted-foreground text-xs" role="status">
          {message}
        </p>
      </div>
    </div>
  );
}
