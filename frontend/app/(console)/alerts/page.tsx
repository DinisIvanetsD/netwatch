import { ShieldCheck } from "lucide-react";
import { AlertList } from "@/components/alerts/alert-list";
import { EmptyState } from "@/components/empty-state";
import { getAlerts } from "@/lib/api";

export const metadata = { title: "Alerts" };

export const dynamic = "force-dynamic";

export default async function AlertsPage() {
  const alerts = await getAlerts();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Review and resolve network change notifications.
        </p>
      </div>
      {alerts.items.length ? (
        <AlertList initial={alerts.items} />
      ) : (
        <EmptyState
          title="No active alerts"
          description="Your network currently has no alerts to review."
          icon={ShieldCheck}
        />
      )}
    </div>
  );
}
