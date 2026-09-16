"use client";

import { useId, useState } from "react";
import { useRouter } from "next/navigation";
import { FlaskConical, Radar } from "lucide-react";

import { updateSettings } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { NetWatchSettings, OperatingMode } from "@/types/settings";

const MODES: {
  value: OperatingMode;
  title: string;
  description: string;
  icon: typeof Radar;
}[] = [
  {
    value: "simulation",
    title: "Simulation",
    description:
      "This device simulates a live network. Virtual devices join and leave, latency changes, and services appear so you can explore NetWatch without scanning a real LAN.",
    icon: FlaskConical,
  },
  {
    value: "live",
    title: "Live sensor",
    description:
      "This device scans the authorized private network and reports the real devices it finds, with real IP, MAC, and hostname evidence.",
    icon: Radar,
  },
];

export function OperatingModeForm({
  initial,
  discoveryMode,
}: {
  initial: NetWatchSettings;
  discoveryMode: "windows_sensor" | "container";
}) {
  const router = useRouter();
  const groupName = useId();
  const [mode, setMode] = useState<OperatingMode>(initial.operating_mode);
  const [saving, setSaving] = useState<OperatingMode | null>(null);
  const [message, setMessage] = useState("");

  async function selectMode(next: OperatingMode) {
    if (next === mode || saving) return;
    const previous = mode;
    setMode(next);
    setSaving(next);
    setMessage("");
    try {
      const updated = await updateSettings({ operating_mode: next });
      setMode(updated.operating_mode);
      setMessage(
        updated.operating_mode === "simulation"
          ? "Simulation mode is active. The dashboard now shows simulated devices."
          : "Live sensor mode is active. Start a scan to discover the real devices.",
      );
      router.refresh();
    } catch (error) {
      setMode(previous);
      setMessage(
        error instanceof Error
          ? error.message
          : "The operating mode could not be changed.",
      );
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="space-y-4">
      <div
        role="radiogroup"
        aria-label="Operating mode"
        className="grid gap-4 sm:grid-cols-2"
      >
        {MODES.map((option) => {
          const Icon = option.icon;
          const active = mode === option.value;
          return (
            <label
              key={option.value}
              className={cn(
                "border-border cursor-pointer rounded-lg border p-4 transition-colors",
                active
                  ? "border-primary/60 bg-primary/5"
                  : "hover:bg-accent/40",
              )}
            >
              <span className="flex items-start gap-3">
                <input
                  type="radio"
                  name={groupName}
                  value={option.value}
                  checked={active}
                  onChange={() => selectMode(option.value)}
                  className="accent-primary mt-1 size-4"
                  aria-describedby={`${groupName}-${option.value}-description`}
                />
                <span>
                  <span className="flex items-center gap-2 text-sm font-medium">
                    <Icon className="size-4" aria-hidden="true" />
                    {option.title}
                    {active ? (
                      <span className="text-primary text-[10px] font-semibold tracking-wide uppercase">
                        Active
                      </span>
                    ) : null}
                  </span>
                  <span
                    id={`${groupName}-${option.value}-description`}
                    className="text-muted-foreground mt-1 block text-xs"
                  >
                    {option.description}
                  </span>
                </span>
              </span>
            </label>
          );
        })}
      </div>
      {mode === "live" && discoveryMode === "container" ? (
        <p className="text-muted-foreground text-xs">
          In-container discovery is limited by the Docker network. Start the
          Windows host sensor on this device for full neighbor and ARP
          enrichment.
        </p>
      ) : null}
      <p className="text-muted-foreground text-xs" role="status">
        {saving ? "Switching operating mode…" : message}
      </p>
      <p className="text-muted-foreground text-xs">
        Inventories stay separate: switching modes never deletes devices,
        history, or alerts recorded by the other mode.
      </p>
    </div>
  );
}
