import Link from "next/link";
import { Ban, Eye, Globe2, MonitorSmartphone, Search } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getAllDevices,
  getInternetActivity,
  getInternetActivitySummary,
} from "@/lib/api";
import {
  deviceDisplayName,
  formatDate,
  formatRelativeTime,
} from "@/lib/format";

export const metadata = { title: "Internet Activity" };
export const dynamic = "force-dynamic";

interface InternetSearchParams {
  device?: string;
  result?: string;
  search?: string;
  hours?: string;
  page?: string;
}

function positiveInteger(value?: string) {
  if (!value) return undefined;
  const parsed = Number.parseInt(value, 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function pageLink(params: InternetSearchParams, page: number) {
  const result = new URLSearchParams();
  for (const [key, value] of Object.entries({
    ...params,
    page: String(page),
  })) {
    if (value) result.set(key, value);
  }
  return `/internet?${result.toString()}`;
}

function categoryLabel(value: string) {
  return value.replaceAll("_", " ");
}

export default async function InternetActivityPage({
  searchParams,
}: {
  searchParams: Promise<InternetSearchParams>;
}) {
  const params = await searchParams;
  const deviceId = positiveInteger(params.device);
  const hours = positiveInteger(params.hours) ?? 24;
  const page = positiveInteger(params.page) ?? 1;
  const blocked =
    params.result === "blocked"
      ? true
      : params.result === "allowed"
        ? false
        : undefined;
  const [activity, summary, devices] = await Promise.all([
    getInternetActivity({
      deviceId,
      blocked,
      search: params.search?.trim() || undefined,
      hours,
      page,
      perPage: 50,
    }),
    getInternetActivitySummary(deviceId, hours),
    getAllDevices({ sortBy: "name", sortOrder: "asc" }),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Internet Activity
        </h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm">
          DNS metadata associated with each local device by IP address.
        </p>
      </div>

      <div className="border-primary/20 bg-primary/5 flex items-start gap-3 rounded-xl border p-4">
        <Eye
          className="text-primary mt-0.5 size-4 shrink-0"
          aria-hidden="true"
        />
        <div>
          <p className="text-sm font-medium">
            What NetWatch can—and cannot—see
          </p>
          <p className="text-muted-foreground mt-1 text-xs leading-5">
            NetWatch can report that a device contacted domains such as
            google.com, youtube.com, or roblox.com when its DNS uses AdGuard
            Home. HTTPS keeps search words, exact videos, messages, passwords,
            and page contents encrypted, so NetWatch does not display or claim
            to know them.
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="DNS REQUESTS"
          value={String(summary.total_queries)}
          detail={`Last ${hours === 24 ? "24 hours" : `${Math.round(hours / 24)} days`}`}
          icon={Globe2}
        />
        <MetricCard
          label="BLOCKED"
          value={String(summary.blocked_queries)}
          detail="Reported by DNS policy"
          icon={Ban}
          tone="warning"
        />
        <MetricCard
          label="ACTIVE DEVICES"
          value={String(summary.active_devices)}
          detail="Matched to inventory"
          icon={MonitorSmartphone}
        />
        <MetricCard
          label="INFERRED SERVICES"
          value={String(summary.top_services.length)}
          detail="Based on contacted domains"
          icon={Search}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Activity filters</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1fr_auto_auto_1.2fr_auto]">
            <NativeSelect
              name="device"
              defaultValue={params.device ?? ""}
              className="w-full"
            >
              <option value="">All devices</option>
              {devices.map((device) => (
                <option key={device.id} value={device.id}>
                  {deviceDisplayName(device)} · {device.ip_address}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect name="result" defaultValue={params.result ?? ""}>
              <option value="">All results</option>
              <option value="allowed">Allowed</option>
              <option value="blocked">Blocked</option>
            </NativeSelect>
            <NativeSelect name="hours" defaultValue={String(hours)}>
              <option value="1">1 hour</option>
              <option value="6">6 hours</option>
              <option value="24">24 hours</option>
              <option value="168">7 days</option>
              <option value="720">30 days</option>
            </NativeSelect>
            <Input
              name="search"
              defaultValue={params.search ?? ""}
              placeholder="Search observed domain"
              aria-label="Search observed domain"
              className="font-mono"
            />
            <Button type="submit">
              <Search />
              Filter
            </Button>
          </form>
        </CardContent>
      </Card>

      {summary.top_domains.length || summary.top_services.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Top domains</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {summary.top_domains.slice(0, 8).map((item, index) => (
                <div
                  key={item.domain}
                  className="flex items-center gap-3 text-sm"
                >
                  <span className="text-muted-foreground w-5 font-mono text-xs">
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1 truncate font-mono text-xs">
                    {item.domain}
                  </span>
                  <Badge variant="secondary">{item.count}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Top inferred services</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {summary.top_services.length ? (
                summary.top_services.slice(0, 8).map((item, index) => (
                  <div
                    key={item.service}
                    className="flex items-center gap-3 text-sm"
                  >
                    <span className="text-muted-foreground w-5 font-mono text-xs">
                      {index + 1}
                    </span>
                    <span className="flex-1">{item.service}</span>
                    <Badge variant="secondary">{item.count} observations</Badge>
                  </div>
                ))
              ) : (
                <p className="text-muted-foreground text-xs">
                  No known service classifications in this period.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {activity.items.length ? (
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Recent DNS activity</CardTitle>
          </CardHeader>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Device</TableHead>
                  <TableHead>Domain</TableHead>
                  <TableHead>Inferred service</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Result</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activity.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell
                      className="text-muted-foreground"
                      title={formatDate(item.timestamp)}
                    >
                      {formatRelativeTime(item.timestamp)}
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/devices/${item.device_id}?tab=internet`}
                        className="hover:text-primary font-medium"
                      >
                        {item.device_name || "Unnamed device"}
                      </Link>
                      <span className="text-muted-foreground mt-1 block font-mono text-xs">
                        {item.source_ip || "IP unavailable"}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {item.domain}
                    </TableCell>
                    <TableCell>{item.service || "Unclassified"}</TableCell>
                    <TableCell className="capitalize">
                      {categoryLabel(item.category)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={item.blocked ? "warning" : "secondary"}>
                        {item.blocked ? "Blocked" : "Allowed"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="border-border flex items-center justify-between border-t p-4 text-xs">
            <span className="text-muted-foreground">
              {activity.total} observations
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                asChild={page > 1}
                disabled={page <= 1}
              >
                {page > 1 ? (
                  <Link href={pageLink(params, page - 1)}>Previous</Link>
                ) : (
                  <span>Previous</span>
                )}
              </Button>
              <Button
                variant="outline"
                size="sm"
                asChild={page < activity.pages}
                disabled={page >= activity.pages}
              >
                {page < activity.pages ? (
                  <Link href={pageLink(params, page + 1)}>Next</Link>
                ) : (
                  <span>Next</span>
                )}
              </Button>
            </div>
          </div>
        </Card>
      ) : (
        <EmptyState
          icon={Globe2}
          title="No DNS activity available"
          description="Confirm that AdGuard Home is connected and that this device sends DNS requests through it. A network scan alone cannot reveal browsing metadata."
        />
      )}
    </div>
  );
}
