import Link from "next/link";
import { Activity, History } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getDeviceMetrics, getDevices } from "@/lib/api";
import { formatLatency } from "@/lib/format";

export const metadata = { title: "History" };

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  const devices = await getDevices({ perPage: 100 });
  const histories = await Promise.all(
    devices.items.map(async (device) => ({
      device,
      metrics: (await getDeviceMetrics(device.id, 100)).items,
    })),
  );
  const withHistory = histories.filter(({ metrics }) => metrics.length > 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">History</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Inspect recorded availability and latency samples by device.
        </p>
      </div>
      {withHistory.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {withHistory.map(({ device, metrics }) => {
            const onlineSamples = metrics.filter((metric) => metric.online);
            const latencies = onlineSamples.flatMap((metric) =>
              metric.latency_ms === null ? [] : [metric.latency_ms],
            );
            const availability = Math.round(
              (onlineSamples.length / metrics.length) * 100,
            );
            const average = latencies.length
              ? latencies.reduce((sum, value) => sum + value, 0) /
                latencies.length
              : null;
            return (
              <Link key={device.id} href={`/devices/${device.id}?tab=history`}>
                <Card className="hover:border-primary/30 h-full transition-colors">
                  <CardHeader>
                    <CardTitle>
                      {device.name ?? device.hostname ?? device.ip_address}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="grid grid-cols-3 gap-3">
                    <HistoryMetric
                      label="Availability"
                      value={`${availability}%`}
                    />
                    <HistoryMetric
                      label="Avg latency"
                      value={formatLatency(average)}
                    />
                    <HistoryMetric
                      label="Samples"
                      value={String(metrics.length)}
                    />
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={History}
          title="No historical data"
          description="Historical metrics will build over time as scheduled scans complete."
        />
      )}
    </div>
  );
}

function HistoryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-muted-foreground text-[10px] font-semibold tracking-wide uppercase">
        {label}
      </p>
      <p className="mt-1 flex items-center gap-1 font-mono text-sm">
        <Activity className="text-primary size-3" aria-hidden="true" />
        {value}
      </p>
    </div>
  );
}
