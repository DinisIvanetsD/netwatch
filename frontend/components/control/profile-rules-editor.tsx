"use client";

import { useState } from "react";
import { Ban, Plus, RefreshCw, Trash2 } from "lucide-react";

import { EnforcementBadge } from "@/components/control/control-status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { createDomainRule, deleteDomainRule, retryDomainRule } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import type { ControlProfile, DomainRule, RuleAction } from "@/types/control";

export function ProfileRulesEditor({ profile }: { profile: ControlProfile }) {
  const [rules, setRules] = useState(profile.domain_rules);
  const [domain, setDomain] = useState("");
  const [action, setAction] = useState<RuleAction>("block");
  const [includeSubdomains, setIncludeSubdomains] = useState(true);
  const [duration, setDuration] = useState("always");
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");

  async function addRule() {
    if (!domain.trim()) {
      setMessage("Enter a domain such as example.com.");
      return;
    }
    const durationMinutes =
      duration === "15m"
        ? 15
        : duration === "1h"
          ? 60
          : duration === "1d"
            ? 1_440
            : null;
    setWorking(true);
    setMessage("");
    try {
      const rule = await createDomainRule({
        scope_type: "profile",
        scope_id: profile.id,
        domain: domain.trim(),
        action,
        include_subdomains: action === "allow" ? true : includeSubdomains,
        reason: `${profile.name} profile custom rule`,
        ...(durationMinutes
          ? {
              expires_at: new Date(
                Date.now() + durationMinutes * 60_000,
              ).toISOString(),
            }
          : {}),
      });
      setRules((current) => [rule, ...current]);
      setDomain("");
      setMessage(
        rule.enforcement_status === "active"
          ? "Rule applied by the DNS provider."
          : rule.enforcement_error || "Rule saved and awaiting enforcement.",
      );
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Rule could not be saved.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function retry(ruleId: number) {
    setWorking(true);
    setMessage("");
    try {
      const updated = await retryDomainRule(ruleId);
      setRules((current) =>
        current.map((rule) => (rule.id === ruleId ? updated : rule)),
      );
      setMessage(updated.enforcement_error || "Rule enforcement retried.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Retry failed.");
    } finally {
      setWorking(false);
    }
  }

  async function remove(rule: DomainRule) {
    setWorking(true);
    setMessage("");
    try {
      await deleteDomainRule(rule.id);
      setRules((current) => current.filter((item) => item.id !== rule.id));
      setMessage(`${rule.domain} was removed from this profile.`);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "The rule could not be safely removed.",
      );
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <span className="bg-primary/10 text-primary rounded-lg p-2">
          <Ban className="size-4" aria-hidden="true" />
        </span>
        <div>
          <h3 className="text-sm font-semibold">Custom website rules</h3>
          <p className="text-muted-foreground mt-1 text-xs leading-5">
            Rules match DNS domains, not encrypted page contents. An allow rule
            can also be temporary.
          </p>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
        <Input
          aria-label="Domain"
          value={domain}
          onChange={(event) => setDomain(event.target.value)}
          placeholder="example.com"
          spellCheck={false}
          className="font-mono"
        />
        <NativeSelect
          aria-label="Rule action"
          value={action}
          onChange={(event) => setAction(event.target.value as RuleAction)}
        >
          <option value="block">Block</option>
          <option value="allow">Allow</option>
        </NativeSelect>
        <NativeSelect
          aria-label="Rule duration"
          value={duration}
          onChange={(event) => setDuration(event.target.value)}
        >
          <option value="always">Always</option>
          <option value="15m">15 minutes</option>
          <option value="1h">1 hour</option>
          <option value="1d">24 hours</option>
        </NativeSelect>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="text-muted-foreground flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={action === "allow" || includeSubdomains}
            disabled={action === "allow"}
            onChange={(event) => setIncludeSubdomains(event.target.checked)}
            className="accent-primary size-4"
          />
          Include subdomains
        </label>
        <Button onClick={addRule} disabled={working || !domain.trim()}>
          <Plus />
          Add rule
        </Button>
      </div>

      {rules.length ? (
        <div className="border-border divide-border divide-y overflow-hidden rounded-lg border">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-mono text-sm">
                    {rule.domain}
                  </span>
                  <span
                    className={
                      rule.action === "block"
                        ? "text-amber-300"
                        : "text-emerald-400"
                    }
                  >
                    {rule.action}
                  </span>
                  <EnforcementBadge status={rule.enforcement_status} />
                </div>
                <p className="text-muted-foreground mt-1 text-xs">
                  {rule.expires_at
                    ? `Expires ${formatRelativeTime(rule.expires_at)}`
                    : "Permanent"}
                  {rule.enforcement_error ? ` · ${rule.enforcement_error}` : ""}
                </p>
              </div>
              <div className="flex gap-2">
                {rule.enforcement_status === "error" ||
                rule.enforcement_status === "pending" ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => retry(rule.id)}
                    disabled={working}
                  >
                    <RefreshCw />
                    Retry
                  </Button>
                ) : null}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => remove(rule)}
                  disabled={working}
                >
                  <Trash2 />
                  Remove
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="border-border text-muted-foreground rounded-lg border border-dashed p-4 text-center text-xs">
          No custom website rules for this profile.
        </p>
      )}
      <p className="text-muted-foreground text-xs" role="status">
        {message}
      </p>
    </div>
  );
}
