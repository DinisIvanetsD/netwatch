import { Ban, Globe2, MonitorSmartphone } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getInternetActivity, getInternetActivitySummary } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";

export const metadata = { title: "Internet Activity" };
export const dynamic = "force-dynamic";

export default async function InternetActivityPage() {
  const [activity, summary] = await Promise.all([
    getInternetActivity(),
    getInternetActivitySummary(),
  ]);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Internet Activity
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          DNS request metadata reported by your configured local provider. This
          is not packet capture or byte usage.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="DNS REQUESTS"
          value={String(summary.total_queries)}
          detail="Last 24 hours"
          icon={Globe2}
        />
        <MetricCard
          label="BLOCKED"
          value={String(summary.blocked_queries)}
          detail="Filtered by DNS policy"
          icon={Ban}
          tone="warning"
        />
        <MetricCard
          label="ACTIVE DEVICES"
          value={String(summary.active_devices)}
          detail="Matched to NetWatch inventory"
          icon={MonitorSmartphone}
        />
      </div>
      {activity.items.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Recent DNS activity</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Domain</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Result</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activity.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="text-muted-foreground">
                      {formatRelativeTime(item.timestamp)}
                    </TableCell>
                    <TableCell className="font-mono">{item.domain}</TableCell>
                    <TableCell className="capitalize">
                      {item.category}
                    </TableCell>
                    <TableCell className="font-mono">
                      {item.query_type ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={item.blocked ? "warning" : "secondary"}>
                        {item.blocked ? "Blocked" : item.response_status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          icon={Globe2}
          title="No DNS activity available"
          description="Configure AdGuard Home in Settings, then run a scan. NetWatch will associate DNS metadata with devices by local IP address."
        />
      )}
    </div>
  );
}
