"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Ban,
  Check,
  Clock3,
  Pencil,
  Router,
  ShieldAlert,
  ShieldCheck,
  UserRoundCheck,
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { runDeviceControlAction, updateDeviceIdentity } from "@/lib/api";
import { deviceDisplayName, formatRelativeTime } from "@/lib/format";
import type {
  AccessAuditList,
  AccessOverview,
  ControlProfile,
  DeviceControlAction,
} from "@/types/control";
import type { Device } from "@/types/device";

type DeviceSection = "unknown" | "quarantined" | "blocked" | "trusted";

const sectionDetails: Record<
  DeviceSection,
  { title: string; description: string; icon: typeof ShieldCheck }
> = {
  unknown: {
    title: "Unknown devices",
    description:
      "Review newly discovered devices without assuming they are malicious.",
    icon: ShieldAlert,
  },
  quarantined: {
    title: "Quarantined devices",
    description:
      "Devices restricted by a compatible router or firewall provider.",
    icon: WifiOff,
  },
  blocked: {
    title: "Blocked devices",
    description:
      "Persistent blocks confirmed by the configured network provider.",
    icon: Ban,
  },
  trusted: {
    title: "Trusted and ignored devices",
    description: "Devices already reviewed by the administrator.",
    icon: ShieldCheck,
  },
};

function belongsToSection(device: Device, section: DeviceSection) {
  if (section === "trusted") {
    return device.trust_state === "trusted" || device.trust_state === "ignored";
  }
  return device.trust_state === section;
}

export function AccessControlManager({
  initial,
  profiles,
  audit,
}: {
  initial: AccessOverview;
  profiles: ControlProfile[];
  audit: AccessAuditList;
}) {
  const [devices, setDevices] = useState(initial.devices);
  const dnsOnlyProvider = initial.provider_id === "technitium_dns_containment";

  function replaceDevice(updated: Device) {
    setDevices((current) =>
      current.map((device) => (device.id === updated.id ? updated : device)),
    );
  }

  const counts = {
    unknown: devices.filter((device) => device.trust_state === "unknown")
      .length,
    quarantined: devices.filter(
      (device) => device.trust_state === "quarantined",
    ).length,
    blocked: devices.filter((device) => device.trust_state === "blocked")
      .length,
    trusted: devices.filter(
      (device) =>
        device.trust_state === "trusted" || device.trust_state === "ignored",
    ).length,
  };
  const providerReady =
    initial.provider_configured && initial.provider_status === "connected";

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Access Control
          </h1>
          <p className="text-muted-foreground mt-1 max-w-3xl text-sm">
            Review device identities and send supported control actions through
            your router or firewall integration.
          </p>
        </div>
        <Badge
          variant={
            providerReady
              ? "success"
              : initial.provider_configured
                ? "warning"
                : "secondary"
          }
        >
          <Router className="size-3" />
          {initial.provider_name}
        </Badge>
      </div>

      {!initial.provider_configured || dnsOnlyProvider ? (
        <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-4">
          <p className="text-sm font-medium">
            {dnsOnlyProvider
              ? "DNS containment available; router control is not configured"
              : "Router control is not configured"}
          </p>
          <p className="text-muted-foreground mt-1 text-xs leading-5">
            {initial.message}{" "}
            {dnsOnlyProvider
              ? "Pause and Block Internet apply an all-domain DNS rule only after NetWatch confirms that device uses Technitium. Direct IP, encrypted DNS, and VPN traffic may bypass it. Full LAN quarantine still requires a compatible router or firewall."
              : "Trust, ignore, rename, and profile assignment work locally. Pause, quarantine, and block remain disabled so NetWatch never pretends a network action succeeded."}
          </p>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {(
          Object.entries(sectionDetails) as Array<
            [DeviceSection, (typeof sectionDetails)[DeviceSection]]
          >
        ).map(([section, details]) => {
          const Icon = details.icon;
          return (
            <Card key={section}>
              <CardContent className="flex items-center gap-4 pt-5">
                <span className="bg-primary/10 text-primary rounded-lg p-2.5">
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                <div>
                  <p className="text-2xl font-semibold">{counts[section]}</p>
                  <p className="text-muted-foreground text-xs">
                    {details.title}
                  </p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {(Object.keys(sectionDetails) as DeviceSection[]).map((section) => {
        const matching = devices.filter((device) =>
          belongsToSection(device, section),
        );
        if (!matching.length && section !== "unknown") return null;
        const details = sectionDetails[section];
        return (
          <Card key={section}>
            <CardHeader className="border-border border-b">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle>{details.title}</CardTitle>
                  <p className="text-muted-foreground mt-1 text-xs">
                    {details.description}
                  </p>
                </div>
                <Badge variant="secondary">{matching.length}</Badge>
              </div>
            </CardHeader>
            <CardContent className="divide-border divide-y p-0">
              {matching.length ? (
                matching.map((device) => (
                  <DeviceAccessRow
                    key={device.id}
                    device={device}
                    profiles={profiles}
                    capabilities={initial.capabilities}
                    dnsOnlyProvider={dnsOnlyProvider}
                    providerReady={providerReady}
                    onChanged={replaceDevice}
                  />
                ))
              ) : (
                <p className="text-muted-foreground p-6 text-center text-sm">
                  No unknown devices need review.
                </p>
              )}
            </CardContent>
          </Card>
        );
      })}

      <Card>
        <CardHeader className="border-border border-b">
          <CardTitle>Control audit log</CardTitle>
          <p className="text-muted-foreground text-xs">
            Successful, failed, and no-change administrator actions are
            retained.
          </p>
        </CardHeader>
        <CardContent className="divide-border divide-y p-0">
          {audit.items.length ? (
            audit.items.slice(0, 20).map((item) => (
              <div
                key={item.id}
                className="grid gap-2 px-5 py-4 text-sm md:grid-cols-[10rem_1fr_auto] md:items-center"
              >
                <div>
                  <p className="font-medium">{item.device_name || "System"}</p>
                  <p className="text-muted-foreground mt-1 text-xs">
                    {formatRelativeTime(item.created_at)}
                  </p>
                </div>
                <p className="text-muted-foreground text-xs leading-5">
                  {item.message}
                </p>
                <Badge
                  variant={
                    item.result === "completed" ? "success" : "secondary"
                  }
                >
                  {item.result.replaceAll("_", " ")}
                </Badge>
              </div>
            ))
          ) : (
            <p className="text-muted-foreground p-6 text-center text-sm">
              No control actions have been recorded yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DeviceAccessRow({
  device,
  profiles,
  capabilities,
  dnsOnlyProvider,
  providerReady,
  onChanged,
}: {
  device: Device;
  profiles: ControlProfile[];
  capabilities: Record<string, boolean>;
  dnsOnlyProvider: boolean;
  providerReady: boolean;
  onChanged: (device: Device) => void;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(
    device.name === device.ip_address ? "" : (device.name ?? ""),
  );
  const [owner, setOwner] = useState(device.owner ?? "");
  const [deviceType, setDeviceType] = useState(device.device_type ?? "");
  const [profileId, setProfileId] = useState(
    device.profile_id ? String(device.profile_id) : "",
  );
  const [working, setWorking] = useState<string | null>(null);
  const [message, setMessage] = useState("");

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
      onChanged(updated);
      setEditing(false);
      setMessage("Device identity saved.");
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Device could not be updated.",
      );
    } finally {
      setWorking(null);
    }
  }

  async function act(action: DeviceControlAction, durationMinutes?: number) {
    setWorking(action);
    setMessage("");
    try {
      const result = await runDeviceControlAction(
        device.id,
        action,
        durationMinutes,
      );
      onChanged(result.device);
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

  const needsResume = device.internet_access !== "allowed";
  const internetCapability = needsResume
    ? "unblock_internet"
    : "block_internet";
  const canInternetAction =
    providerReady && Boolean(capabilities[internetCapability]);
  const canQuarantine = Boolean(
    providerReady &&
    capabilities[
      device.trust_state === "quarantined"
        ? "release_device"
        : "quarantine_device"
    ],
  );
  const canBlock = providerReady && Boolean(capabilities.firewall_rules);

  return (
    <div className="p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center">
        <div className="min-w-0 xl:w-64">
          <Link
            href={`/devices/${device.id}`}
            className="hover:text-primary block truncate text-sm font-semibold"
          >
            {deviceDisplayName(device)}
          </Link>
          <p className="text-muted-foreground mt-1 font-mono text-xs">
            {device.ip_address}
          </p>
          <p className="text-muted-foreground mt-1 truncate text-xs">
            {device.vendor || "Vendor unknown"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 xl:w-64">
          <TrustBadge state={device.trust_state} />
          <InternetAccessBadge state={device.internet_access} />
        </div>
        <div className="flex flex-1 flex-wrap gap-2 xl:justify-end">
          {device.trust_state !== "trusted" ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => act("trust")}
              disabled={
                working !== null ||
                device.trust_state === "quarantined" ||
                device.trust_state === "blocked"
              }
            >
              <UserRoundCheck />
              Trust
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="outline"
            onClick={() => setEditing((value) => !value)}
            disabled={working !== null}
          >
            <Pencil />
            Edit name
          </Button>
          <span
            title={
              canInternetAction ? undefined : "Router integration required"
            }
          >
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                act(needsResume ? "resume-internet" : "pause-internet", 60)
              }
              disabled={working !== null || !canInternetAction}
            >
              <Clock3 />
              {needsResume
                ? "Resume Internet"
                : dnsOnlyProvider
                  ? "Pause via DNS 1 hour"
                  : "Pause 1 hour"}
            </Button>
          </span>
          {!needsResume ? (
            <ConfirmAction
              title={`Block Internet for ${deviceDisplayName(device)}?`}
              description={
                dnsOnlyProvider
                  ? "NetWatch will apply a persistent all-domain DNS block after confirming this device uses Technitium. Direct IP, DoH, and VPN traffic can bypass DNS-only containment."
                  : "NetWatch will request a persistent Internet block through the configured network provider."
              }
              actionLabel={dnsOnlyProvider ? "Block via DNS" : "Block Internet"}
              destructive
              disabled={
                working !== null ||
                !providerReady ||
                !capabilities.block_internet
              }
              disabledReason="A compatible DNS, router, or firewall provider is required"
              onConfirm={() => act("block-internet")}
            />
          ) : null}
          <ConfirmAction
            title={
              device.trust_state === "quarantined"
                ? `Release ${deviceDisplayName(device)}?`
                : `Quarantine ${deviceDisplayName(device)}?`
            }
            description={
              device.trust_state === "quarantined"
                ? "The router will restore the access allowed by its release policy."
                : "A compatible router or firewall will restrict Internet and LAN access. DNS-only containment cannot provide LAN quarantine."
            }
            actionLabel={
              device.trust_state === "quarantined" ? "Release" : "Quarantine"
            }
            disabled={working !== null || !canQuarantine}
            disabledReason="Router integration required"
            onConfirm={() =>
              act(
                device.trust_state === "quarantined" ? "release" : "quarantine",
              )
            }
          />
          <ConfirmAction
            title={`Block ${deviceDisplayName(device)}?`}
            description="This requests a persistent network block through the configured router or firewall. The displayed state changes only after provider confirmation."
            actionLabel="Block device"
            destructive
            disabled={working !== null || !canBlock}
            disabledReason="Router firewall capability required"
            onConfirm={() => act("block")}
          />
        </div>
      </div>

      {editing ? (
        <div className="border-border bg-muted/20 mt-4 grid gap-3 rounded-lg border p-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="text-xs font-medium">
            Display name
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Living Room TV"
              className="mt-2"
            />
          </label>
          <label className="text-xs font-medium">
            Owner
            <Input
              value={owner}
              onChange={(event) => setOwner(event.target.value)}
              placeholder="Household member"
              className="mt-2"
            />
          </label>
          <label className="text-xs font-medium">
            Device type
            <Input
              value={deviceType}
              onChange={(event) => setDeviceType(event.target.value)}
              placeholder="phone, TV, laptop…"
              className="mt-2"
            />
          </label>
          <label className="text-xs font-medium">
            Profile
            <NativeSelect
              value={profileId}
              onChange={(event) => setProfileId(event.target.value)}
              className="mt-2 w-full"
            >
              <option value="">Unassigned</option>
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </NativeSelect>
          </label>
          <div className="flex gap-2 md:col-span-2 xl:col-span-4">
            <Button
              size="sm"
              onClick={saveIdentity}
              disabled={working !== null}
            >
              <Check />
              Save identity
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
      {message ? (
        <p className="text-muted-foreground mt-3 text-xs" role="status">
          {message}
        </p>
      ) : null}
    </div>
  );
}

function ConfirmAction({
  title,
  description,
  actionLabel,
  destructive = false,
  disabled,
  disabledReason,
  onConfirm,
}: {
  title: string;
  description: string;
  actionLabel: string;
  destructive?: boolean;
  disabled: boolean;
  disabledReason: string;
  onConfirm: () => void;
}) {
  return (
    <span title={disabled ? disabledReason : undefined}>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button
            size="sm"
            variant={destructive ? "destructive" : "outline"}
            disabled={disabled}
          >
            {destructive ? <Ban /> : <ShieldAlert />}
            {actionLabel}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{title}</AlertDialogTitle>
            <AlertDialogDescription>{description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onConfirm}>
              {actionLabel}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </span>
  );
}
