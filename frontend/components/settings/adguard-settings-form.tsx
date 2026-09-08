"use client";

import { useState } from "react";
import { CheckCircle2, Link2, Save } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { configureAdGuard, testAdGuard } from "@/lib/api";
import type { AdGuardIntegration } from "@/types/integration";

export function AdGuardSettingsForm({
  initial,
}: {
  initial: AdGuardIntegration | null;
}) {
  const [serverUrl, setServerUrl] = useState(initial?.server_url ?? "");
  const [username, setUsername] = useState(initial?.username ?? "");
  const [password, setPassword] = useState("");
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [status, setStatus] = useState(initial?.status ?? "not_configured");
  const [message, setMessage] = useState(
    initial?.message ?? "Connect AdGuard Home to show real DNS activity.",
  );
  const [working, setWorking] = useState<"test" | "save" | null>(null);

  async function testConnection() {
    if (!password) {
      setMessage("Enter the AdGuard Home password to test the connection.");
      return;
    }
    setWorking("test");
    try {
      const result = await testAdGuard({
        server_url: serverUrl.trim(),
        username: username.trim(),
        password,
      });
      setStatus(result.status);
      setMessage(result.message);
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
    setWorking("save");
    try {
      const result = await configureAdGuard({
        server_url: serverUrl.trim(),
        username: username.trim(),
        ...(password ? { password } : {}),
        enabled,
      });
      setStatus(result.status);
      setMessage(result.message);
      setPassword("");
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
          <p className="text-sm font-medium">DNS visibility and filtering</p>
          <p className="text-muted-foreground mt-1 max-w-2xl text-xs">
            Uses the local AdGuard Home API. NetWatch never claims traffic-byte
            visibility from DNS logs.
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

      <div className="grid gap-4 md:grid-cols-3">
        <Field label="Server URL" htmlFor="adguard-url">
          <Input
            id="adguard-url"
            value={serverUrl}
            onChange={(event) => setServerUrl(event.target.value)}
            placeholder="http://192.168.1.2:3000"
            spellCheck={false}
            className="font-mono"
          />
        </Field>
        <Field label="Username" htmlFor="adguard-username">
          <Input
            id="adguard-username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
          />
        </Field>
        <Field
          label={
            initial?.password_set
              ? "Password (leave blank to keep)"
              : "Password"
          }
          htmlFor="adguard-password"
        >
          <Input
            id="adguard-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </Field>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="outline"
          onClick={testConnection}
          disabled={working !== null}
        >
          <Link2 />
          {working === "test" ? "Testing…" : "Test connection"}
        </Button>
        <Button
          onClick={save}
          disabled={working !== null || !serverUrl || !username}
        >
          <Save />
          {working === "save" ? "Saving…" : "Save integration"}
        </Button>
        <p className="text-muted-foreground text-xs" role="status">
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
