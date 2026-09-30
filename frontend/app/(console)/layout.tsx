import { DashboardShell } from "@/components/layout/dashboard-shell";
import { getAlerts, getNetworkStatus, getSettings } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ConsoleLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [networkResult, alertsResult, settingsResult] =
    await Promise.allSettled([getNetworkStatus(), getAlerts(), getSettings()]);
  const network =
    networkResult.status === "fulfilled" ? networkResult.value : null;
  const activeAlerts =
    alertsResult.status === "fulfilled"
      ? alertsResult.value.items.filter((alert) => !alert.resolved).length
      : 0;
  const operatingMode =
    settingsResult.status === "fulfilled"
      ? settingsResult.value.operating_mode
      : "live";

  return (
    <DashboardShell
      operatingMode={operatingMode}
      lastCompletedScan={network?.last_completed_scan ?? null}
      scanRunning={network?.scan_running ?? false}
      activeAlerts={activeAlerts}
    >
      {children}
    </DashboardShell>
  );
}
