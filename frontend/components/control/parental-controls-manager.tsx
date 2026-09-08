"use client";

import { useMemo, useState } from "react";
import {
  CalendarClock,
  Plus,
  Save,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react";

import { ProfileRulesEditor } from "@/components/control/profile-rules-editor";
import { ProfileScheduleEditor } from "@/components/control/profile-schedule-editor";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  assignProfileDevices,
  createControlProfile,
  deleteControlProfile,
  updateControlProfile,
} from "@/lib/api";
import { deviceDisplayName, formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  ControlProfile,
  ControlProfileInput,
  ControlProfileList,
} from "@/types/control";
import type { Device } from "@/types/device";
import type { ProviderCapability } from "@/types/integration";

function scheduleLabel(profile: ControlProfile) {
  if (profile.schedule_state === "blocked_by_profile")
    return "Disabled by profile";
  if (profile.schedule_state === "blocked_by_schedule")
    return "Outside schedule";
  if (profile.schedule_state === "allowed_by_schedule")
    return "Inside schedule";
  return "Always allowed";
}

function ProfileCard({
  profile,
  active,
  onSelect,
}: {
  profile: ControlProfile;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "border-border bg-card hover:border-primary/40 w-full rounded-xl border p-4 text-start transition-colors",
        active && "border-primary/50 bg-primary/5",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold">{profile.name}</p>
          <p className="text-muted-foreground mt-1 line-clamp-2 text-xs leading-5">
            {profile.description || "No profile description."}
          </p>
        </div>
        <Badge variant={profile.internet_enabled ? "success" : "warning"}>
          {profile.internet_enabled ? "Enabled" : "Disabled"}
        </Badge>
      </div>
      <div className="text-muted-foreground mt-4 grid grid-cols-3 gap-2 text-xs">
        <div>
          <span className="text-foreground block text-base font-semibold">
            {profile.device_count}
          </span>
          Devices
        </div>
        <div>
          <span className="text-foreground block text-base font-semibold">
            {profile.blocked_requests_today}
          </span>
          Blocked today
        </div>
        <div>
          <span className="text-foreground block text-xs leading-6 font-medium">
            {scheduleLabel(profile)}
          </span>
          Schedule
        </div>
      </div>
    </button>
  );
}

export function ParentalControlsManager({
  initial,
  devices,
  dnsProvider,
  networkProvider,
}: {
  initial: ControlProfileList;
  devices: Device[];
  dnsProvider?: ProviderCapability;
  networkProvider?: ProviderCapability;
}) {
  const [profiles, setProfiles] = useState(initial.items);
  const [selectedId, setSelectedId] = useState(initial.items[0]?.id ?? null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const selected =
    profiles.find((profile) => profile.id === selectedId) ?? null;

  function replaceProfile(updated: ControlProfile) {
    setProfiles((current) =>
      current.map((profile) => (profile.id === updated.id ? updated : profile)),
    );
  }

  async function createProfile() {
    if (!newName.trim()) return;
    setWorking(true);
    setMessage("");
    try {
      const created = await createControlProfile({
        name: newName.trim(),
        description: "Custom household access profile.",
        internet_enabled: true,
        safe_search_enabled: false,
        blocked_categories: [],
      });
      setProfiles((current) => [...current, created]);
      setSelectedId(created.id);
      setCreating(false);
      setNewName("");
      setMessage("Profile created.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Profile could not be created.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function removeProfile() {
    if (!selected) return;
    setWorking(true);
    setMessage("");
    try {
      await deleteControlProfile(selected.id);
      const remaining = profiles.filter(
        (profile) => profile.id !== selected.id,
      );
      setProfiles(remaining);
      setSelectedId(remaining[0]?.id ?? null);
      setMessage("Profile deleted. Assigned devices are now unassigned.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Profile could not be safely deleted.",
      );
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Parental Controls
          </h1>
          <p className="text-muted-foreground mt-1 max-w-3xl text-sm">
            Assign devices to household profiles, save Internet schedules, and
            enforce custom DNS rules through supported providers.
          </p>
        </div>
        <Button onClick={() => setCreating((value) => !value)}>
          <Plus />
          New profile
        </Button>
      </div>

      {creating ? (
        <Card>
          <CardContent className="flex flex-col gap-3 pt-5 sm:flex-row">
            <Input
              aria-label="New profile name"
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder="Teen"
              maxLength={80}
            />
            <Button
              onClick={createProfile}
              disabled={working || !newName.trim()}
            >
              Create profile
            </Button>
            <Button variant="ghost" onClick={() => setCreating(false)}>
              Cancel
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {profiles.map((profile) => (
          <ProfileCard
            key={profile.id}
            profile={profile}
            active={profile.id === selectedId}
            onSelect={() => setSelectedId(profile.id)}
          />
        ))}
      </div>

      {selected ? (
        <ProfileWorkspace
          key={selected.id}
          profile={selected}
          devices={devices}
          categories={initial.categories}
          dnsProvider={dnsProvider}
          networkProvider={networkProvider}
          onChanged={replaceProfile}
          onDelete={removeProfile}
          working={working}
        />
      ) : (
        <Card>
          <CardContent className="text-muted-foreground py-10 text-center text-sm">
            Create a profile to begin configuring household policies.
          </CardContent>
        </Card>
      )}
      <p className="text-muted-foreground text-xs" role="status">
        {message}
      </p>
    </div>
  );
}

function ProfileWorkspace({
  profile,
  devices,
  categories,
  dnsProvider,
  networkProvider,
  onChanged,
  onDelete,
  working,
}: {
  profile: ControlProfile;
  devices: Device[];
  categories: Record<string, string>;
  dnsProvider?: ProviderCapability;
  networkProvider?: ProviderCapability;
  onChanged: (profile: ControlProfile) => void;
  onDelete: () => void;
  working: boolean;
}) {
  const [form, setForm] = useState<ControlProfileInput>({
    name: profile.name,
    description: profile.description,
    internet_enabled: profile.internet_enabled,
    safe_search_enabled: profile.safe_search_enabled,
    blocked_categories: profile.blocked_categories,
  });
  const [deviceIds, setDeviceIds] = useState(profile.device_ids);
  const [saving, setSaving] = useState<"profile" | "devices" | null>(null);
  const [message, setMessage] = useState("");

  async function saveProfile() {
    setSaving("profile");
    setMessage("");
    try {
      const updated = await updateControlProfile(profile.id, form);
      onChanged(updated);
      setMessage("Profile policy saved.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Profile could not be saved.",
      );
    } finally {
      setSaving(null);
    }
  }

  async function saveAssignments() {
    setSaving("devices");
    setMessage("");
    try {
      const updated = await assignProfileDevices(profile.id, deviceIds);
      onChanged(updated);
      setMessage("Device assignments saved and DNS rules reconciled.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Assignments could not be saved.",
      );
    } finally {
      setSaving(null);
    }
  }

  const assignedElsewhere = useMemo(
    () =>
      new Set(
        devices
          .filter(
            (device) =>
              device.profile_id !== null && device.profile_id !== profile.id,
          )
          .map((device) => device.id),
      ),
    [devices, profile.id],
  );

  const categoryEnforced = Boolean(
    dnsProvider?.capabilities.category_filtering,
  );
  const safeSearchAvailable = Boolean(dnsProvider?.capabilities.safe_search);
  const scheduleEnforced = Boolean(
    networkProvider?.capabilities.block_internet,
  );

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="border-border flex-row items-start justify-between gap-4 border-b">
          <div>
            <CardTitle className="text-base">Manage {profile.name}</CardTitle>
            <p className="text-muted-foreground mt-1 text-xs">
              Current state: {scheduleLabel(profile)}
              {profile.next_schedule_change
                ? ` · changes ${formatRelativeTime(profile.next_schedule_change)}`
                : ""}
            </p>
          </div>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="sm" disabled={working}>
                <Trash2 />
                Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete {profile.name}?</AlertDialogTitle>
                <AlertDialogDescription>
                  Devices will become unassigned. NetWatch will first remove any
                  provider-managed domain rules so it cannot leave orphaned
                  blocks.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={onDelete}>
                  Delete profile
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </CardHeader>
        <CardContent className="space-y-5 pt-5">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium">
              Profile name
              <Input
                value={form.name}
                onChange={(event) =>
                  setForm({ ...form, name: event.target.value })
                }
                className="mt-2"
                maxLength={80}
              />
            </label>
            <label className="text-sm font-medium">
              Description
              <Input
                value={form.description ?? ""}
                onChange={(event) =>
                  setForm({ ...form, description: event.target.value })
                }
                className="mt-2"
                maxLength={300}
              />
            </label>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <PolicyToggle
              label="Internet policy enabled"
              description="Master preference for this profile."
              checked={form.internet_enabled}
              onChange={(value) =>
                setForm({ ...form, internet_enabled: value })
              }
            />
            <PolicyToggle
              label="Safe Search requested"
              description={
                safeSearchAvailable
                  ? "Provider supports global Safe Search; configure enforcement in Settings."
                  : "Current DNS provider cannot enforce Safe Search."
              }
              checked={form.safe_search_enabled}
              onChange={(value) =>
                setForm({ ...form, safe_search_enabled: value })
              }
            />
          </div>
          <Button
            onClick={saveProfile}
            disabled={saving !== null || !form.name.trim()}
          >
            <Save />
            {saving === "profile" ? "Saving…" : "Save profile"}
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Users className="text-primary size-4" aria-hidden="true" />
              <CardTitle>Assigned devices</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="border-border divide-border max-h-72 divide-y overflow-y-auto rounded-lg border">
              {devices.map((device) => (
                <label
                  key={device.id}
                  className="hover:bg-muted/30 flex cursor-pointer items-center gap-3 px-3 py-3"
                >
                  <input
                    type="checkbox"
                    checked={deviceIds.includes(device.id)}
                    onChange={(event) =>
                      setDeviceIds((current) =>
                        event.target.checked
                          ? [...current, device.id]
                          : current.filter((id) => id !== device.id),
                      )
                    }
                    className="accent-primary size-4"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">
                      {deviceDisplayName(device)}
                    </span>
                    <span className="text-muted-foreground font-mono text-xs">
                      {device.ip_address}
                    </span>
                  </span>
                  {assignedElsewhere.has(device.id) ? (
                    <Badge variant="secondary">Reassign</Badge>
                  ) : null}
                </label>
              ))}
            </div>
            <Button onClick={saveAssignments} disabled={saving !== null}>
              <Save />
              {saving === "devices" ? "Saving…" : "Save assignments"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ShieldCheck className="text-primary size-4" aria-hidden="true" />
              <CardTitle>Blocked categories</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.entries(categories).map(([value, label]) => (
                <label
                  key={value}
                  className="border-border hover:bg-muted/30 flex cursor-pointer items-center gap-2 rounded-lg border p-3 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={form.blocked_categories.includes(value)}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        blocked_categories: event.target.checked
                          ? [...form.blocked_categories, value]
                          : form.blocked_categories.filter(
                              (category) => category !== value,
                            ),
                      })
                    }
                    className="accent-primary size-4"
                  />
                  {label}
                </label>
              ))}
            </div>
            <p className="text-muted-foreground text-xs leading-5">
              {categoryEnforced
                ? "The current DNS provider reports category-filtering support."
                : "Saved as policy preferences only: the current DNS provider does not expose per-profile category filtering. Custom domain rules below remain enforceable."}
            </p>
            <Button
              onClick={saveProfile}
              disabled={saving !== null}
              variant="outline"
            >
              <Save />
              Save categories
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <CalendarClock className="text-primary size-4" aria-hidden="true" />
            <CardTitle>Schedule policy</CardTitle>
          </div>
          {!scheduleEnforced ? (
            <p className="text-muted-foreground text-xs">
              Stored and evaluated by NetWatch; automatic network enforcement
              requires a compatible router integration.
            </p>
          ) : null}
        </CardHeader>
        <CardContent>
          <ProfileScheduleEditor profile={profile} onSaved={onChanged} />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-5">
          <ProfileRulesEditor profile={profile} />
        </CardContent>
      </Card>

      <p className="text-muted-foreground text-xs" role="status">
        {message}
      </p>
    </div>
  );
}

function PolicyToggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="border-border flex items-center justify-between gap-4 rounded-lg border p-4">
      <span>
        <span className="block text-sm font-medium">{label}</span>
        <span className="text-muted-foreground mt-1 block text-xs leading-5">
          {description}
        </span>
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="accent-primary size-4 shrink-0"
      />
    </label>
  );
}
