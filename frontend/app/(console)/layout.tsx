import { DashboardShell } from "@/components/layout/dashboard-shell";

export default function ConsoleLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const demoMode = process.env.NETWATCH_DEMO_MODE === "true";
  return <DashboardShell demoMode={demoMode}>{children}</DashboardShell>;
}
