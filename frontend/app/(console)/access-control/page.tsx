import { AccessControlManager } from "@/components/control/access-control-manager";
import {
  getAccessAudit,
  getAccessOverview,
  getControlProfiles,
} from "@/lib/api";

export const metadata = { title: "Access Control" };
export const dynamic = "force-dynamic";

export default async function AccessControlPage() {
  const [overview, profiles, audit] = await Promise.all([
    getAccessOverview(),
    getControlProfiles(),
    getAccessAudit(),
  ]);
  return (
    <AccessControlManager
      initial={overview}
      profiles={profiles.items}
      audit={audit}
    />
  );
}
