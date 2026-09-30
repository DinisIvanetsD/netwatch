import { NetworkReport } from "@/components/reports/network-report";
import { getAlerts, getAllDevices, getInternetActivity } from "@/lib/api";
import type { InternetActivityItem } from "@/types/internet-activity";

export const metadata = { title: "Network Report" };
export const dynamic = "force-dynamic";

export default async function ReportsPage() {
  const [devicesResult, alertsResult] = await Promise.allSettled([
    getAllDevices({ sortBy: "name", sortOrder: "asc" }),
    getAlerts(),
  ]);
  const devices =
    devicesResult.status === "fulfilled" ? devicesResult.value : [];
  const alerts =
    alertsResult.status === "fulfilled" ? alertsResult.value.items : [];
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
    <NetworkReport data={{ devices, alerts, dnsActivity, dnsAvailable }} />
  );
}
