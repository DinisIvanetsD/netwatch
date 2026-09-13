"use client";

import { useState } from "react";
import { CheckCircle2, Link2, Save, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { configureTechnitium, testTechnitium } from "@/lib/api";
import type { TechnitiumIntegration } from "@/types/integration";

export function TechnitiumSettingsForm({
  initial,
}: {
  initial: TechnitiumIntegration | null;
}) {
  const [serverUrl, setServerUrl] = useState(initial?.server_url ?? "");
  const [username, setUsername] = useState(initial?.username ?? "admin");
  const [password, setPassword] = useState("");
  const [dnsPort, setDnsPort] = useState(String(initial?.dns_port ?? 53));
  const [passwordSet, setPasswordSet] = useState(
    initial?.password_set ?? false,
  );
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [status, setStatus] = useState(initial?.status ?? "not_configured");
  const [message, setMessage] = useState(
    getStatusMessage(
      initial?.status ?? "not_configured",
      initial?.message ??
        "Connect Technitium to collect DNS metadata and enforce website rules.",
    ),
  );
  const [working, setWorking] = useState<"test" | "save" | null>(null);

  async function testConnection() {
    if (!password && !passwordSet) {
      setMessage("Enter the Technitium password to test the connection.");
      return;
    }
    setWorking("test");
    try {
      const result = await testTechnitium({
        server_url: serverUrl.trim(),
        username: username.trim(),
        ...(password ? { password } : {}),
      });
      setStatus(result.status);
      setMessage(getStatusMessage(result.status, result.message));
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof Error ? error.message : "Connection test failed.",
      );
    } finally {
      setWorking(null);
    }
  }

  async function save() {
    const parsedPort = Number.parseInt(dnsPort, 10);
    if (
      !Number.isInteger(parsedPort) ||
      parsedPort < 1 ||
      parsedPort > 65_535
    ) {
      setMessage("DNS port must be between 1 and 65535.");
      return;
    }
    setWorking("save");
    try {
      const result = await configureTechnitium({
        server_url: serverUrl.trim(),
        username: username.trim(),
        ...(password ? { password } : {}),
        dns_port: parsedPort,
        enabled,
      });
      setStatus(result.status);
      setMessage(getStatusMessage(result.status, result.message));
      setPasswordSet(result.password_set);
      setPassword("");
      setDnsPort(String(result.dns_port));
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Integration could not be saved.",
      );
    } finally {
      setWorking(null);
    }
  }

  const connected = status === "connected";
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-sm font-medium">
            <ShieldCheck className="text-primary size-4" aria-hidden="true" />
            DNS intelligence and policy engine
          </p>
          <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-5">
            The bundled Technitium server provides query history, statistics,
            block lists, and client policy groups. DNS reveals contacted
            domains, not encrypted page contents, messages, passwords, or search
            terms.
          </p>
        </div>
        <Badge variant={connected ? "success" : "secondary"}>
          {connected && <CheckCircle2 className="size-3" />}
          {status.replaceAll("_", " ")}
        </Badge>
      </div>

      <label className="flex items-center justify-between gap-4">
        <span className="text-sm font-medium">Integration enabled</span>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
          className="accent-primary size-4"
        />
      </label>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Field label="Server URL" htmlFor="technitium-url">
          <div>
            <Input
              id="technitium-url"
              value={serverUrl}
              onChange={(event) => setServerUrl(event.target.value)}
              placeholder="http://192.168.1.2:5380"
              spellCheck={false}
              className="font-mono"
              aria-describedby="technitium-url-help"
            />
            <p
              id="technitium-url-help"
              className="text-muted-foreground mt-2 text-xs leading-5"
            >
              Use <span className="font-mono">http://127.0.0.1:5380</span> for
              Technitium on this Windows PC, or{" "}
              <span className="font-mono">http://technitium:5380</span> when
              NetWatch runs in Docker. For a remote private host, use its
              private LAN address on port 5380. This must point to
              Technitium&apos;s web/API console, not DNS port 53.
            </p>
          </div>
        </Field>
        <Field label="Username" htmlFor="technitium-username">
          <Input
            id="technitium-username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
          />
        </Field>
        <Field
          label={passwordSet ? "Password (leave blank to keep)" : "Password"}
          htmlFor="technitium-password"
        >
          <Input
            id="technitium-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </Field>
        <Field label="Client DNS port" htmlFor="technitium-dns-port">
          <Input
            id="technitium-dns-port"
            type="number"
            min={1}
            max={65_535}
            value={dnsPort}
            onChange={(event) => setDnsPort(event.target.value)}
            className="font-mono"
          />
        </Field>
      </div>

      <p className="text-muted-foreground rounded-lg border p-3 text-xs leading-5">
        <span className="font-medium">How to connect / recover:</span> The
        username is normally the Technitium admin account. If you forgot the
        password, reset or change it in Technitium first; NetWatch cannot
        recover it. Leave Password blank to reuse the stored encrypted
        credential only when the Server URL and username are unchanged.
      </p>

      {dnsPort !== "53" ? (
        <p className="border-warning/30 bg-warning/5 text-muted-foreground rounded-lg border p-3 text-xs leading-5">
          Port {dnsPort} is suitable for local testing. Most routers and phones
          require standard DNS port 53 for automatic network-wide use.
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="outline"
          onClick={testConnection}
          disabled={working !== null || !serverUrl || !username}
          aria-busy={working === "test"}
          aria-describedby="technitium-status"
        >
          <Link2 />
          {working === "test" ? "Testing…" : "Test connection"}
        </Button>
        <Button
          onClick={save}
          disabled={working !== null || !serverUrl || !username}
          aria-busy={working === "save"}
          aria-describedby="technitium-status"
        >
          <Save />
          {working === "save" ? "Preparing apps…" : "Save and prepare"}
        </Button>
        <p
          id="technitium-status"
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

function getStatusMessage(status: string, fallback: string) {
  switch (status) {
    case "rate_limited":
      return "Technitium temporarily rate-limited this request. Wait before trying again; do not retry repeatedly.";
    case "authentication_failed":
    case "authentication_failure":
    case "auth_failed":
      return "The Technitium password was not accepted. Verify it in Technitium, then try again.";
    case "disconnected":
      return "NetWatch is disconnected from Technitium. Check the Server URL, network access, and that Technitium is running.";
    case "connected":
      return fallback || "Connected to Technitium.";
    default:
      return fallback;
  }
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
