import { Check, Minus, ServerCog } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ProviderCapability } from "@/types/integration";

const labels: Record<string, string> = {
  query_history: "DNS history",
  per_client_history: "Per-device DNS activity",
  domain_blocking: "Website blocking",
  client_rules: "Client-specific website rules",
  category_filtering: "Category filtering",
  safe_search: "Safe Search",
  statistics: "DNS statistics",
  filter_lists: "Managed filter lists",
  dns_enforcement: "Force approved DNS",
  traffic_bytes: "Upload / download bytes",
  list_clients: "Router client inventory",
  client_status: "Router client status",
  block_internet: "Pause / block Internet",
  unblock_internet: "Restore Internet",
  quarantine_device: "Quarantine device",
  release_device: "Release device",
  disconnect_client: "Disconnect client",
  bandwidth_metrics: "Bandwidth metrics",
  firewall_rules: "Persistent device block",
};

export function ProviderCapabilityMatrix({
  providers,
}: {
  providers: ProviderCapability[];
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {providers.map((provider) => (
        <div
          key={`${provider.kind}-${provider.provider_id}`}
          className="border-border rounded-lg border p-4"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="bg-primary/10 text-primary rounded-lg p-2">
                <ServerCog className="size-4" />
              </span>
              <div>
                <p className="text-sm font-semibold">{provider.display_name}</p>
                <p className="text-muted-foreground mt-1 text-xs leading-5">
                  {provider.message}
                </p>
              </div>
            </div>
            <Badge variant={provider.configured ? "success" : "secondary"}>
              {provider.configured ? "Configured" : "Fallback"}
            </Badge>
          </div>
          <div className="border-border mt-4 divide-y border-t">
            {Object.entries(provider.capabilities).map(
              ([capability, supported]) => (
                <div
                  key={capability}
                  className="flex items-center justify-between gap-3 py-2 text-xs"
                >
                  <span>
                    {labels[capability] ?? capability.replaceAll("_", " ")}
                  </span>
                  {supported ? (
                    <Check
                      className="size-4 text-emerald-400"
                      aria-label="Supported"
                    />
                  ) : (
                    <Minus
                      className="text-muted-foreground size-4"
                      aria-label="Unavailable"
                    />
                  )}
                </div>
              ),
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
