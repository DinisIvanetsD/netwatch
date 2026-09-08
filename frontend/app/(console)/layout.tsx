import { DashboardShell } from "@/components/layout/dashboard-shell";
import { getAlerts, getNetworkStatus } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ConsoleLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const demoMode = process.env.NETWATCH_DEMO_MODE === "true";
  const [network, alerts] = await Promise.all([
    getNetworkStatus(),
    getAlerts(),
  ]);
  const activeAlerts = alerts.items.filter((alert) => !alert.resolved).length;

  return (
    <DashboardShell
      demoMode={demoMode}
      lastCompletedScan={network.last_completed_scan}
      scanRunning={network.scan_running}
      activeAlerts={activeAlerts}
    >
      {children}
    </DashboardShell>
  );
}
