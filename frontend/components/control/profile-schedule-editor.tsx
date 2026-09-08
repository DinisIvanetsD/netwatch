"use client";

import { useState } from "react";
import { Clock3, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { replaceProfileSchedules } from "@/lib/api";
import type { AccessScheduleInput, ControlProfile } from "@/types/control";

const days = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

interface DaySchedule extends AccessScheduleInput {
  start: string;
  end: string;
}

function minuteToTime(value: number) {
  const normalized = value === 1_440 ? 0 : value;
  return `${String(Math.floor(normalized / 60)).padStart(2, "0")}:${String(normalized % 60).padStart(2, "0")}`;
}

function timeToMinute(value: string, end = false) {
  const [hours, minutes] = value.split(":").map(Number);
  if (end && hours === 0 && minutes === 0) return 1_440;
  return hours * 60 + minutes;
}

function scheduleRows(profile: ControlProfile): DaySchedule[] {
  return days.map((_, weekday) => {
    const existing = profile.schedules.find(
      (schedule) => schedule.weekday === weekday && schedule.enabled,
    );
    return {
      weekday,
      start_minute: existing?.start_minute ?? 7 * 60,
      end_minute: existing?.end_minute ?? 22 * 60,
      enabled: Boolean(existing),
      start: minuteToTime(existing?.start_minute ?? 7 * 60),
      end: minuteToTime(existing?.end_minute ?? 22 * 60),
    };
  });
}

export function ProfileScheduleEditor({
  profile,
  onSaved,
}: {
  profile: ControlProfile;
  onSaved: (profile: ControlProfile) => void;
}) {
  const [rows, setRows] = useState(() => scheduleRows(profile));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  function updateRow(weekday: number, values: Partial<DaySchedule>) {
    setRows((current) =>
      current.map((row) =>
        row.weekday === weekday ? { ...row, ...values } : row,
      ),
    );
  }

  async function save() {
    const enabled = rows.filter((row) => row.enabled);
    if (
      enabled.some(
        (row) => timeToMinute(row.start) >= timeToMinute(row.end, true),
      )
    ) {
      setMessage("Each end time must be later than its start time.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const updated = await replaceProfileSchedules(
        profile.id,
        enabled.map((row) => ({
          weekday: row.weekday,
          start_minute: timeToMinute(row.start),
          end_minute: timeToMinute(row.end, true),
          enabled: true,
        })),
      );
      onSaved(updated);
      setMessage("Internet schedule saved.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Schedule could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <span className="bg-primary/10 text-primary rounded-lg p-2">
          <Clock3 className="size-4" aria-hidden="true" />
        </span>
        <div>
          <h3 className="text-sm font-semibold">Internet schedule</h3>
          <p className="text-muted-foreground mt-1 text-xs leading-5">
            These are allowed Internet windows. Enforcement requires a router
            provider with timed access-control support.
          </p>
        </div>
      </div>

      <div className="border-border divide-border divide-y overflow-hidden rounded-lg border">
        {rows.map((row) => (
          <div
            key={row.weekday}
            className="grid gap-3 px-3 py-3 sm:grid-cols-[8rem_1fr_1fr] sm:items-center"
          >
            <label className="flex items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                checked={row.enabled}
                onChange={(event) =>
                  updateRow(row.weekday, { enabled: event.target.checked })
                }
                className="accent-primary size-4"
              />
              {days[row.weekday]}
            </label>
            <input
              aria-label={`${days[row.weekday]} start time`}
              type="time"
              value={row.start}
              disabled={!row.enabled}
              onChange={(event) =>
                updateRow(row.weekday, { start: event.target.value })
              }
              className="border-input bg-background h-9 rounded-md border px-3 font-mono text-sm disabled:opacity-40"
            />
            <input
              aria-label={`${days[row.weekday]} end time`}
              type="time"
              value={row.end}
              disabled={!row.enabled}
              onChange={(event) =>
                updateRow(row.weekday, { end: event.target.value })
              }
              className="border-input bg-background h-9 rounded-md border px-3 font-mono text-sm disabled:opacity-40"
            />
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={save} disabled={saving}>
          <Save />
          {saving ? "Saving…" : "Save schedule"}
        </Button>
        <p className="text-muted-foreground text-xs" role="status">
          {message}
        </p>
      </div>
    </div>
  );
}
