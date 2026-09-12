import Link from "next/link";
import { Check, CircleAlert, CircleDashed } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/format";
import type { InternetActivityDiagnostics } from "@/types/internet-activity";
import type {
  ProviderCapability,
  TechnitiumIntegration,
} from "@/types/integration";
import type { NetworkStatus } from "@/types/network";
import type { ReadinessResponse } from "@/types/readiness";

type ChecklistItem = {
  label: string;
  detail: string;
  complete: boolean;
  optional?: boolean;
  href?: string;
};

export function SetupChecklist({
  network,
  technitium,
  providers,
  diagnostics,
  readiness,
}: {
  network: NetworkStatus;
  technitium: TechnitiumIntegration | null;
  providers: ProviderCapability[];
  diagnostics: InternetActivityDiagnostics | null;
  readiness?: ReadinessResponse | null;
}) {
  const dnsProvider = providers.find((provider) => provider.kind === "dns");
  const networkProvider = providers.find(
    (provider) => provider.kind === "network",
  );
  const routerReady = Boolean(
    networkProvider?.configured &&
    networkProvider.status === "connected" &&
    (networkProvider?.capabilities.quarantine_device ||
      networkProvider?.capabilities.firewall_rules),
  );
  const items: ChecklistItem[] = [
    {
      label: "Network detected",
      detail: network.local_ip
        ? `${network.subnet} via ${network.local_ip}`
        : "Waiting for a local network address.",
      complete: readiness
        ? readiness.checks.network_identity?.status === "ready"
        : Boolean(network.local_ip && network.subnet),
      href: "#network-readiness",
    },
    {
      label: "Technitium configured",
      detail:
        technitium?.message ??
        "Add a Technitium DNS server to inspect DNS activity.",
      complete:
        readiness?.checks.technitium?.status === "ready" ||
        Boolean(technitium?.enabled && technitium.status === "connected"),
      href: "#technitium",
    },
    {
      label: "DNS routing confirmed",
      detail:
        diagnostics?.message ??
        "Route client DNS through the PC address shown below.",
      complete: readiness
        ? readiness.checks.technitium?.status === "ready" &&
          diagnostics?.status === "ready"
        : diagnostics?.status === "ready",
      href: "#network-readiness",
    },
    {
      label: "Router control available",
      detail: routerReady
        ? "A compatible enforcement capability is connected."
        : "Optional for DNS visibility; required for full device or LAN quarantine.",
      complete: routerReady,
      optional: true,
      href: "#router-integration",
    },
    {
      label: "First scan completed",
      detail: network.last_completed_scan
        ? `Completed ${formatDate(network.last_completed_scan)}.`
        : network.scan_running
          ? "A network scan is currently running."
          : "Run an authorized scan to build the device inventory.",
      complete: Boolean(
        network.last_completed_scan || network.total_devices > 0,
      ),
      href: "/devices",
    },
  ];
  const requiredItems = items.filter((item) => !item.optional);
  const completed = requiredItems.filter((item) => item.complete).length;

  return (
    <Card aria-labelledby="setup-checklist-title">
      <CardHeader className="border-border border-b">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle id="setup-checklist-title">First-run setup</CardTitle>
            <p className="text-muted-foreground mt-1 text-xs leading-5">
              Complete the essentials in order. Router control is optional when
              you only need DNS activity.
            </p>
          </div>
          <Badge
            variant={completed === requiredItems.length ? "success" : "warning"}
            aria-label={`${completed} of ${requiredItems.length} required setup steps complete`}
          >
            {completed} of {requiredItems.length} required complete
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-5">
        <ol
          className="grid gap-3 md:grid-cols-2 xl:grid-cols-5"
          aria-label="First-run setup checklist"
        >
          {items.map((item, index) => {
            const Icon = item.complete
              ? Check
              : item.href
                ? CircleAlert
                : CircleDashed;
            const content = (
              <div className="flex h-full gap-3 rounded-lg border p-3">
                <Icon
                  className={
                    item.complete
                      ? "mt-0.5 size-4 shrink-0 text-emerald-400"
                      : "mt-0.5 size-4 shrink-0 text-amber-300"
                  }
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <p className="text-xs font-semibold">
                    {index + 1}. {item.label}
                    {item.optional ? " · Optional" : ""}
                  </p>
                  <p className="text-muted-foreground mt-1 text-[11px] leading-4">
                    {item.detail}
                  </p>
                  <span className="sr-only">
                    {item.complete ? "Complete" : "Needs attention"}
                  </span>
                </div>
              </div>
            );
            return (
              <li key={item.label}>
                {item.href ? (
                  <Link
                    href={item.href}
                    className="hover:border-primary focus-visible:ring-ring block h-full focus-visible:ring-2 focus-visible:outline-none"
                  >
                    {content}
                  </Link>
                ) : (
                  content
                )}
              </li>
            );
          })}
        </ol>
        {dnsProvider && diagnostics?.status !== "ready" ? (
          <p className="text-muted-foreground mt-4 text-xs">
            DNS status is based on observed query routing, not just provider
            configuration.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
