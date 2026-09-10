"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Router, Save, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { configureRouter, deleteRouterIntegration } from "@/lib/api";
import type {
  ProviderCapability,
  RouterIntegration,
  RouterProviderId,
} from "@/types/integration";

const providerOptions: { id: RouterProviderId; label: string }[] = [
  { id: "openwrt", label: "OpenWrt" },
  { id: "opnsense", label: "OPNsense" },
  { id: "nos", label: "NOS (manual fallback)" },
  { id: "hitron", label: "Hitron (manual fallback)" },
];

const capabilityLabels: Record<string, string> = {
  list_clients: "Router client inventory",
  client_status: "Router client status",
  block_internet: "Pause / block Internet",
  unblock_internet: "Restore Internet",
  quarantine_device: "Quarantine device",
  release_device: "Release device",
  firewall_rules: "Persistent device block",
};

export function RouterSettingsForm({
  initial,
  capability,
}: {
  initial: RouterIntegration | null;
  capability?: ProviderCapability;
}) {
  const initialProvider = providerOptions.some(
    (option) => option.id === initial?.provider_id,
  )
    ? (initial?.provider_id as RouterProviderId)
    : "nos";
  const [providerId, setProviderId] =
    useState<RouterProviderId>(initialProvider);
  const [serverUrl, setServerUrl] = useState(
    initial?.server_url ?? "http://192.168.1.1",
  );
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [enabled, setEnabled] = useState(initial?.enabled ?? false);
  const [confirmed, setConfirmed] = useState(false);
  const [status, setStatus] = useState(initial?.status ?? "not_configured");
  const [message, setMessage] = useState(
    initial?.message ?? "No router integration is configured.",
  );
  const [working, setWorking] = useState<"save" | "delete" | null>(null);
  const router = useRouter();

  const manual =
    providerId === "nos" || providerId === "hitron" || providerId === "generic";
  const canSave =
    Boolean(serverUrl.trim()) && !working && (!enabled || confirmed);
  const selectedCapability =
    capability?.provider_id === providerId ? capability : undefined;

  async function save() {
    if (!canSave) {
      setMessage(
        enabled
          ? "Confirm that NetWatch may change router state before enabling control."
          : "Enter a router URL.",
      );
      return;
    }
    setWorking("save");
    try {
      const result = await configureRouter({
        provider_id: providerId,
        server_url: serverUrl.trim(),
        enabled,
        confirm_state_changes: confirmed,
        ...(providerId === "openwrt" && username
          ? { username: username.trim() }
          : {}),
        ...(providerId === "openwrt" && password ? { password } : {}),
        ...(providerId === "opnsense" && apiKey ? { api_key: apiKey } : {}),
        ...(providerId === "opnsense" && apiSecret
          ? { api_secret: apiSecret }
          : {}),
      });
      setStatus(result.status);
      setMessage(result.message);
      setPassword("");
      setApiKey("");
      setApiSecret("");
      router.refresh();
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Router integration could not be saved.",
      );
    } finally {
      setWorking(null);
    }
  }

  async function remove() {
    setWorking("delete");
    try {
      await deleteRouterIntegration();
      setEnabled(false);
      setConfirmed(false);
      setStatus("not_configured");
      setMessage("Router integration removed.");
      router.refresh();
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Router integration could not be removed.",
      );
    } finally {
      setWorking(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-sm font-medium">
            <Router className="text-primary size-4" aria-hidden="true" />
            Network control integration
          </p>
          <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-5">
            OpenWrt and OPNsense can automate firewall controls. NOS and Hitron
            are manual fallbacks; NetWatch will not claim automatic enforcement
            for them.
          </p>
        </div>
        <Badge variant={status === "connected" ? "success" : "secondary"}>
          {status === "connected" && <CheckCircle2 className="size-3" />}
          {status.replaceAll("_", " ")}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Router provider" htmlFor="router-provider">
          <select
            id="router-provider"
            value={providerId}
            onChange={(event) =>
              setProviderId(event.target.value as RouterProviderId)
            }
            className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm"
          >
            {providerOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Router URL" htmlFor="router-url">
          <Input
            id="router-url"
            value={serverUrl}
            onChange={(event) => setServerUrl(event.target.value)}
            placeholder="http://192.168.1.1"
            spellCheck={false}
            className="font-mono"
          />
        </Field>
        {providerId === "openwrt" ? (
          <>
            <Field label="Username" htmlFor="router-username">
              <Input
                id="router-username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
              />
            </Field>
            <Field
              label="Password (leave blank to keep)"
              htmlFor="router-password"
            >
              <Input
                id="router-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
              />
            </Field>
          </>
        ) : null}
        {providerId === "opnsense" ? (
          <>
            <Field
              label="API key (leave blank to keep)"
              htmlFor="router-api-key"
            >
              <Input
                id="router-api-key"
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                autoComplete="off"
              />
            </Field>
            <Field
              label="API secret (leave blank to keep)"
              htmlFor="router-api-secret"
            >
              <Input
                id="router-api-secret"
                type="password"
                value={apiSecret}
                onChange={(event) => setApiSecret(event.target.value)}
                autoComplete="off"
              />
            </Field>
          </>
        ) : null}
      </div>

      <label className="flex items-start gap-3 text-sm">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
          className="accent-primary mt-0.5 size-4"
        />
        <span>
          <span className="font-medium">Integration enabled</span>
          <span className="text-muted-foreground mt-1 block text-xs">
            Disabled keeps the current provider inactive.
          </span>
        </span>
      </label>
      <label className="border-border bg-muted/20 flex items-start gap-3 rounded-lg border p-3 text-sm">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
          className="accent-primary mt-0.5 size-4"
        />
        <span>
          <span className="font-medium">
            I confirm NetWatch may change router/firewall state when supported.
          </span>
          <span className="text-muted-foreground mt-1 block text-xs">
            Required before enabling control. Credentials are never shown or
            prefilled.
          </span>
        </span>
      </label>

      <div className="border-border rounded-lg border p-3 text-xs">
        <p className="font-medium">Capabilities</p>
        {selectedCapability ? (
          <>
            <p className="text-muted-foreground mt-1">
              Reported by the backend for {selectedCapability.display_name} (
              {selectedCapability.status.replaceAll("_", " ")}).
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(selectedCapability.capabilities)
                .filter(([key]) => capabilityLabels[key])
                .map(([key, supported]) => (
                  <span
                    key={key}
                    className={
                      supported ? "text-emerald-400" : "text-muted-foreground"
                    }
                  >
                    {supported ? "✓" : "—"} {capabilityLabels[key]}
                  </span>
                ))}
            </div>
          </>
        ) : (
          <p className="text-muted-foreground mt-1">
            {manual
              ? "Manual controls only; automatic router capabilities are unavailable."
              : "Capabilities will be verified after this provider is saved."}
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          onClick={save}
          disabled={!canSave}
          aria-busy={working === "save"}
        >
          <Save />
          {working === "save" ? "Saving…" : "Save router integration"}
        </Button>
        {initial ? (
          <Button
            variant="outline"
            onClick={remove}
            disabled={Boolean(working)}
            aria-busy={working === "delete"}
          >
            <Trash2 />
            {working === "delete" ? "Removing…" : "Remove integration"}
          </Button>
        ) : null}
        <p
          className="text-muted-foreground text-xs"
          role="status"
          aria-live="polite"
        >
          {message}
        </p>
      </div>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-2 block text-sm font-medium">
        {label}
      </label>
      {children}
    </div>
  );
}
