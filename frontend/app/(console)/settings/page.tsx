import { ServiceSettingsForm } from "@/components/settings/service-settings-form";
import { AlertSettingsForm } from "@/components/settings/alert-settings-form";
import { DataSettingsForm } from "@/components/settings/data-settings-form";
import { ScannerSettingsForm } from "@/components/settings/scanner-settings-form";
import { TechnitiumSettingsForm } from "@/components/settings/technitium-settings-form";
import { RouterSettingsForm } from "@/components/settings/router-settings-form";
import { AccessPolicyForm } from "@/components/settings/access-policy-form";
import { ProviderCapabilityMatrix } from "@/components/settings/provider-capability-matrix";
import { SafeSearchSettingsForm } from "@/components/settings/safe-search-settings-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getProviderCapabilities,
  getRouterIntegration,
  getSafeSearch,
  getSettings,
  getTechnitiumConfiguration,
} from "@/lib/api";

export const metadata = { title: "Settings" };

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const [settings, technitium, router, providers] = await Promise.all([
    getSettings(),
    getTechnitiumConfiguration(),
    getRouterIntegration(),
    getProviderCapabilities(),
  ]);
  const dnsProvider = providers.items.find(
    (provider) => provider.kind === "dns",
  );
  const networkProvider = providers.items.find(
    (provider) => provider.kind === "network",
  );
  const safeSearchAvailable = Boolean(
    dnsProvider?.configured && dnsProvider.capabilities.safe_search,
  );
  const safeSearch = safeSearchAvailable
    ? await getSafeSearch().catch(() => null)
    : null;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Configure the authorized network and scanner behavior.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Router integration</CardTitle>
          </CardHeader>
          <CardContent>
            <RouterSettingsForm initial={router} capability={networkProvider} />
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Network and scanner</CardTitle>
          </CardHeader>
          <CardContent>
            <ScannerSettingsForm initial={settings} />
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Provider capability matrix</CardTitle>
          </CardHeader>
          <CardContent>
            <ProviderCapabilityMatrix providers={providers.items} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Access control</CardTitle>
          </CardHeader>
          <CardContent>
            <AccessPolicyForm
              initial={settings}
              routerControlAvailable={Boolean(
                networkProvider?.capabilities.quarantine_device ||
                networkProvider?.capabilities.firewall_rules,
              )}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Safe Search</CardTitle>
          </CardHeader>
          <CardContent>
            <SafeSearchSettingsForm
              initial={safeSearch}
              available={safeSearchAvailable}
              providerName={dnsProvider?.display_name ?? "No DNS provider"}
            />
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Technitium DNS Server</CardTitle>
          </CardHeader>
          <CardContent>
            <TechnitiumSettingsForm initial={technitium} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Service scanner</CardTitle>
          </CardHeader>
          <CardContent>
            <ServiceSettingsForm initial={settings} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Alert rules</CardTitle>
          </CardHeader>
          <CardContent>
            <AlertSettingsForm initial={settings} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Data retention</CardTitle>
          </CardHeader>
          <CardContent>
            <DataSettingsForm initial={settings} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
