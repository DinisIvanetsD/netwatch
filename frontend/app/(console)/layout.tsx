import { DashboardShell } from "@/components/layout/dashboard-shell";
import { getAlerts, getNetworkStatus, getSettings } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ConsoleLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [network, alerts, settings] = await Promise.all([
    getNetworkStatus(),
    getAlerts(),
    getSettings(),
  ]);
  const activeAlerts = alerts.items.filter((alert) => !alert.resolved).length;

  return (
    <DashboardShell
      operatingMode={settings.operating_mode}
      lastCompletedScan={network.last_completed_scan}
      scanRunning={network.scan_running}
      activeAlerts={activeAlerts}
    >
      {children}
    </DashboardShell>
  );
}
