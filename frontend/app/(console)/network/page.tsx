import { Network } from "lucide-react";
import { SectionPage } from "@/components/section-page";

export const metadata = { title: "Network" };

export default function NetworkPage() {
  return (
    <SectionPage
      title="Network"
      description="Review subnet configuration, scan health and discovered network structure."
      emptyTitle="Network map unavailable"
      emptyDescription="A gateway-centered device map will appear once discovery has produced network data."
      icon={Network}
    />
  );
}
