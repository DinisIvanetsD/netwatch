import { ServiceSettingsForm } from "@/components/settings/service-settings-form";
import { AlertSettingsForm } from "@/components/settings/alert-settings-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getSettings } from "@/lib/api";

export const metadata = { title: "Settings" };

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const settings = await getSettings();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Configure the authorized network and scanner behavior.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Network</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <SettingRow label="Monitored subnet" value={settings.subnet} />
            <SettingRow
              label="Scan interval"
              value={`${settings.scan_interval} seconds`}
            />
            <SettingRow
              label="Offline threshold"
              value={`${settings.offline_after_missed_scans} missed scans`}
            />
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
      </div>
    </div>
  );
}

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground text-sm">{label}</span>
      <span className="font-mono text-sm">{value}</span>
    </div>
  );
}
