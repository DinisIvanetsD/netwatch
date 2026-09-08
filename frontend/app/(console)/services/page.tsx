import Link from "next/link";
import { Radar } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { getServices } from "@/lib/api";
import { describeService } from "@/lib/service-descriptions";

export const metadata = { title: "Services" };

export const dynamic = "force-dynamic";

export default async function ServicesPage() {
  const services = await getServices();
  const groups = Map.groupBy(services.items, (service) => service.service_name);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Services</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Approved TCP services observed across discovered devices.
        </p>
      </div>
      {groups.size ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[...groups].map(([name, observations]) => (
            <Card key={name}>
              <CardHeader className="flex-row items-center justify-between">
                <div className="group/service flex items-center gap-2">
                  <CardTitle>{name}</CardTitle>
                  <InfoTooltip
                    label={describeService(name, observations[0].port)}
                    showOnParentHover
                  />
                </div>
                <Badge variant="secondary">
                  {observations.length} device
                  {observations.length === 1 ? "" : "s"}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-2">
                {observations.map((service) => (
                  <Link
                    key={service.id}
                    href={`/devices/${service.device_id}?tab=${service.device_name === "Unnamed device" ? "access" : "services"}`}
                    className="border-border hover:bg-muted/50 flex items-center justify-between rounded-lg border p-3 transition-colors"
                  >
                    <span>
                      <span className="block text-sm font-medium">
                        {service.device_name || "Unnamed device"}
                      </span>
                      <span className="text-muted-foreground mt-0.5 block text-[10px] font-medium tracking-wide uppercase">
                        {service.device_name === "Unnamed device"
                          ? "Click to set name"
                          : "Device name"}
                      </span>
                      <span className="text-muted-foreground font-mono text-xs">
                        {service.ip_address}
                      </span>
                    </span>
                    <span className="font-mono text-xs">
                      {service.protocol.toUpperCase()} {service.port}
                    </span>
                  </Link>
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Radar}
          title="No services observed"
          description="Service checks are optional and only run against approved ports on discovered local devices."
        />
      )}
    </div>
  );
}
