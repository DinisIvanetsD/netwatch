import { ParentalControlsManager } from "@/components/control/parental-controls-manager";
import {
  getAllDevices,
  getControlProfiles,
  getProviderCapabilities,
} from "@/lib/api";

export const metadata = { title: "Parental Controls" };
export const dynamic = "force-dynamic";

export default async function ParentalControlsPage() {
  const [profiles, devices, providers] = await Promise.all([
    getControlProfiles(),
    getAllDevices({ sortBy: "name", sortOrder: "asc" }),
    getProviderCapabilities(),
  ]);

  return (
    <ParentalControlsManager
      initial={profiles}
      devices={devices}
      dnsProvider={providers.items.find((provider) => provider.kind === "dns")}
      networkProvider={providers.items.find(
        (provider) => provider.kind === "network",
      )}
    />
  );
}
