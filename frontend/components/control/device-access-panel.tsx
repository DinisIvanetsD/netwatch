"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Ban,
  Check,
  Clock3,
  ShieldAlert,
  ShieldCheck,
  WifiOff,
} from "lucide-react";

import {
  InternetAccessBadge,
  TrustBadge,
} from "@/components/control/control-status-badge";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { runDeviceControlAction, updateDeviceIdentity } from "@/lib/api";
import { deviceDisplayName } from "@/lib/format";
import type { ControlProfile, DeviceControlAction } from "@/types/control";
import type { Device } from "@/types/device";
import type { ProviderCapability } from "@/types/integration";

export function DeviceAccessPanel({
  initial,
  profiles,
  provider,
}: {
  initial: Device;
  profiles: ControlProfile[];
  provider?: ProviderCapability;
}) {
  const router = useRouter();
  const [device, setDevice] = useState(initial);
  const [name, setName] = useState(
    initial.name === initial.ip_address ? "" : (initial.name ?? ""),
  );
  const [owner, setOwner] = useState(initial.owner ?? "");
  const [deviceType, setDeviceType] = useState(initial.device_type ?? "");
  const [profileId, setProfileId] = useState(
    initial.profile_id ? String(initial.profile_id) : "",
  );
  const [working, setWorking] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const capabilities = provider?.capabilities ?? {};

  async function saveIdentity() {
    setWorking("identity");
    setMessage("");
    try {
      const updated = await updateDeviceIdentity(device.id, {
        name: name.trim() || null,
        owner: owner.trim() || null,
        device_type: deviceType.trim() || null,
        profile_id: profileId ? Number(profileId) : null,
      });
      setDevice(updated);
      setMessage("Device identity and profile saved.");
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Device could not be updated.",
      );
    } finally {
      setWorking(null);
    }
  }

  async function act(action: DeviceControlAction, minutes?: number) {
    setWorking(action);
    setMessage("");
    try {
      const result = await runDeviceControlAction(device.id, action, minutes);
      setDevice(result.device);
      setMessage(result.message);
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Control action failed.",
      );
    } finally {
      setWorking(null);
    }
  }

  const networkUnavailable = !provider?.configured;
  const pauseCapability =
    device.internet_access === "allowed"
      ? "block_internet"
      : "unblock_internet";
  const quarantineCapability =
    device.trust_state === "quarantined"
      ? "release_device"
      : "quarantine_device";

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Device identity</CardTitle>
          <p className="text-muted-foreground text-xs">
            Names and profile assignments are administrator-managed and persist
            across scans.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Display name">
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="João's iPad"
              />
            </Field>
            <Field label="Owner">
              <Input
                value={owner}
                onChange={(event) => setOwner(event.target.value)}
                placeholder="Household member"
              />
            </Field>
            <Field label="Device type">
              <Input
                value={deviceType}
                onChange={(event) => setDeviceType(event.target.value)}
                placeholder="phone, laptop, TV…"
              />
            </Field>
            <Field label="Parental profile">
              <NativeSelect
                value={profileId}
                onChange={(event) => setProfileId(event.target.value)}
                className="w-full"
              >
                <option value="">Unassigned</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}
                  </option>
                ))}
              </NativeSelect>
            </Field>
          </div>
          <Button onClick={saveIdentity} disabled={working !== null}>
            <Check />
            {working === "identity" ? "Saving…" : "Save identity"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-border border-b">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Access control</CardTitle>
              <p className="text-muted-foreground mt-1 text-xs">
                Provider: {provider?.display_name ?? "not configured"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <TrustBadge state={device.trust_state} />
              <InternetAccessBadge state={device.internet_access} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 pt-5">
          {networkUnavailable ? (
            <p className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-3 text-xs leading-5">
              Router integration required for network enforcement. Buttons
              remain disabled and the current device state will not be changed
              falsely.
            </p>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-3">
            <StatusItem
              label="Internet access"
              value={device.internet_access}
            />
            <StatusItem label="LAN access" value={device.lan_access} />
            <StatusItem label="Trust state" value={device.trust_state} />
          </div>
          <div className="flex flex-wrap gap-2">
            {device.trust_state !== "trusted" ? (
              <Button
                variant="outline"
                onClick={() => act("trust")}
                disabled={
                  working !== null ||
                  device.trust_state === "quarantined" ||
                  device.trust_state === "blocked"
                }
              >
                <ShieldCheck />
                Trust device
              </Button>
            ) : (
              <Button
                variant="outline"
                onClick={() => act("ignore")}
                disabled={working !== null}
              >
                Ignore device
              </Button>
            )}
            <span
              title={
                capabilities[pauseCapability]
                  ? undefined
                  : "Router integration required"
              }
            >
              <Button
                variant="outline"
                onClick={() =>
                  act(
                    device.internet_access === "allowed"
                      ? "pause-internet"
                      : "resume-internet",
                    60,
                  )
                }
                disabled={working !== null || !capabilities[pauseCapability]}
              >
                <Clock3 />
                {device.internet_access === "allowed"
                  ? "Pause Internet 1 hour"
                  : "Resume Internet"}
              </Button>
            </span>
            <ConfirmControl
              title={
                device.trust_state === "quarantined"
                  ? `Release ${deviceDisplayName(device)}?`
                  : `Quarantine ${deviceDisplayName(device)}?`
              }
              description="NetWatch will request this action through the configured router and update the state only after confirmation."
              label={
                device.trust_state === "quarantined" ? "Release" : "Quarantine"
              }
              icon={WifiOff}
              disabled={working !== null || !capabilities[quarantineCapability]}
              onConfirm={() =>
                act(
                  device.trust_state === "quarantined"
                    ? "release"
                    : "quarantine",
                )
              }
            />
            <ConfirmControl
              title={`Block ${deviceDisplayName(device)}?`}
              description="This requests a persistent network block. Use it only for a device you have identified and are authorized to control."
              label="Block device"
              icon={Ban}
              destructive
              disabled={working !== null || !capabilities.firewall_rules}
              onConfirm={() => act("block")}
            />
          </div>
          <p className="text-muted-foreground text-xs" role="status">
            {message}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="space-y-2 text-sm font-medium">
      <span className="block">{label}</span>
      {children}
    </label>
  );
}

function StatusItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-border rounded-lg border p-3">
      <p className="text-muted-foreground text-[10px] font-semibold tracking-wide uppercase">
        {label}
      </p>
      <p className="mt-2 text-sm font-medium capitalize">
        {value.replaceAll("_", " ")}
      </p>
    </div>
  );
}

function ConfirmControl({
  title,
  description,
  label,
  icon: Icon,
  destructive = false,
  disabled,
  onConfirm,
}: {
  title: string;
  description: string;
  label: string;
  icon: typeof ShieldAlert;
  destructive?: boolean;
  disabled: boolean;
  onConfirm: () => void;
}) {
  return (
    <span title={disabled ? "Router integration required" : undefined}>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button
            variant={destructive ? "destructive" : "outline"}
            disabled={disabled}
          >
            <Icon />
            {label}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{title}</AlertDialogTitle>
            <AlertDialogDescription>{description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onConfirm}>{label}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </span>
  );
}
