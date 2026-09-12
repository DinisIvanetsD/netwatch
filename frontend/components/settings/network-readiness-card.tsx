"use client";

import { useState } from "react";
import { Check, Copy, ExternalLink, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { InternetActivityDiagnostics } from "@/types/internet-activity";
import type { NetworkStatus } from "@/types/network";

export function NetworkReadinessCard({
  network,
  diagnostics,
}: {
  network: NetworkStatus;
  diagnostics: InternetActivityDiagnostics | null;
}) {
  const [copied, setCopied] = useState(false);
  const ready = diagnostics?.status === "ready";
  const dnsTarget = network.local_ip ?? "the PC LAN address";

  async function copyDnsTarget() {
    if (!network.local_ip) return;
    try {
      await navigator.clipboard.writeText(network.local_ip);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Card className={ready ? "border-emerald-500/25" : "border-amber-500/25"}>
      <CardHeader className="border-border border-b">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Network enforcement readiness</CardTitle>
            <p className="text-muted-foreground mt-1 text-xs leading-5">
              This check separates what NetWatch can do locally from what the
              router must permit.
            </p>
          </div>
          <Badge variant={ready ? "success" : "warning"}>
            {ready ? (
              <Check className="size-3" />
            ) : (
              <TriangleAlert className="size-3" />
            )}
            {ready ? "DNS activity ready" : "DNS routing required"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <ReadinessValue
            label="Monitored network"
            value={network.subnet}
            mono
          />
          <ReadinessValue
            label="Gateway"
            value={network.gateway ?? "Not detected"}
            mono
          />
          <ReadinessValue
            label="PC address for router DNS"
            value={dnsTarget}
            mono
          />
          <ReadinessValue
            label="Technitium DNS port"
            value={`UDP/TCP ${diagnostics?.dns_port ?? 53}`}
            mono
          />
        </div>

        <div className="border-border bg-muted/20 rounded-lg border p-4">
          <p className="text-sm font-medium">
            {ready
              ? "At least one current device is using Technitium."
              : "Other devices are not yet sending DNS through Technitium."}
          </p>
          <p className="text-muted-foreground mt-1 text-xs leading-5">
            {diagnostics?.message ??
              "Connect Technitium and configure the router DHCP DNS address."}
          </p>
          {!ready ? (
            <ol className="text-muted-foreground mt-3 list-decimal space-y-1 pl-4 text-xs leading-5">
              <li>
                In the router LAN/DHCP settings, set the primary DNS to{" "}
                {dnsTarget}.
              </li>
              <li>Reconnect each device to renew its DHCP settings.</li>
              <li>Open a website, then refresh Internet Activity.</li>
            </ol>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={copyDnsTarget}
            disabled={!network.local_ip}
          >
            {copied ? <Check /> : <Copy />}
            {copied ? "Copied" : "Copy PC DNS address"}
          </Button>
          {network.gateway ? (
            <Button asChild type="button" variant="outline" size="sm">
              <a
                href={`http://${network.gateway}`}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink />
                Open router settings
              </a>
            </Button>
          ) : null}
        </div>

        <p className="text-muted-foreground text-xs leading-5">
          DNS blocking only works for clients that use this DNS server. Full
          device blocking and LAN quarantine still require a supported OpenWrt
          or OPNsense firewall integration. pfSense and NOS/Hitron remain manual
          unless a verified control API is configured. A mobile hotspot may not
          expose the DHCP/DNS controls needed for this setup.
        </p>
      </CardContent>
    </Card>
  );
}

function ReadinessValue({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="border-border rounded-lg border p-3">
      <p className="text-muted-foreground text-[10px] font-semibold tracking-wide uppercase">
        {label}
      </p>
      <p
        className={`mt-2 truncate text-sm font-medium ${mono ? "font-mono" : ""}`}
        title={value}
      >
        {value}
      </p>
    </div>
  );
}
