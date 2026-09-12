import { NetworkReport } from "@/components/reports/network-report";
import { getAlerts, getAllDevices, getInternetActivity } from "@/lib/api";
import type { InternetActivityItem } from "@/types/internet-activity";

export const metadata = { title: "Network Report" };
export const dynamic = "force-dynamic";

export default async function ReportsPage() {
  const [devices, alerts] = await Promise.all([
    getAllDevices({ sortBy: "name", sortOrder: "asc" }),
    getAlerts(),
  ]);
  let dnsActivity: InternetActivityItem[] = [];
  let dnsAvailable = true;
  try {
    dnsActivity = (
      await getInternetActivity({ page: 1, perPage: 100, hours: 24 })
    ).items;
  } catch {
    dnsAvailable = false;
  }
  return (
    <NetworkReport
      data={{ devices, alerts: alerts.items, dnsActivity, dnsAvailable }}
    />
  );
}
