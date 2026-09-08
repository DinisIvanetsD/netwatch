import { ServiceSettingsForm } from "@/components/settings/service-settings-form";
import { AlertSettingsForm } from "@/components/settings/alert-settings-form";
import { DataSettingsForm } from "@/components/settings/data-settings-form";
import { ScannerSettingsForm } from "@/components/settings/scanner-settings-form";
import { AdGuardSettingsForm } from "@/components/settings/adguard-settings-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAdGuardConfiguration, getSettings } from "@/lib/api";

export const metadata = { title: "Settings" };

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const [settings, adGuard] = await Promise.all([
    getSettings(),
    getAdGuardConfiguration(),
  ]);
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
            <CardTitle>Network and scanner</CardTitle>
          </CardHeader>
          <CardContent>
            <ScannerSettingsForm initial={settings} />
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>AdGuard Home integration</CardTitle>
          </CardHeader>
          <CardContent>
            <AdGuardSettingsForm initial={adGuard} />
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
