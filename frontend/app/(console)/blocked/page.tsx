import Link from "next/link";
import { Ban, Search } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { GlobalRulesManager } from "@/components/control/global-rules-manager";
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
  getBlockedRequests,
  getControlProfiles,
  getDomainRules,
} from "@/lib/api";
import {
  deviceDisplayName,
  formatDate,
  formatRelativeTime,
} from "@/lib/format";

export const metadata = { title: "Website Blocking" };
export const dynamic = "force-dynamic";

interface BlockedSearchParams {
  device?: string;
  profile?: string;
  category?: string;
  domain?: string;
  hours?: string;
  page?: string;
}

function positiveInteger(value?: string) {
  if (!value) return undefined;
  const parsed = Number.parseInt(value, 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function pageLink(params: BlockedSearchParams, page: number) {
  const next = new URLSearchParams();
  for (const [key, value] of Object.entries({
    ...params,
    page: String(page),
  })) {
    if (value) next.set(key, value);
  }
  return `/blocked?${next.toString()}`;
}

export default async function BlockedRequestsPage({
  searchParams,
}: {
  searchParams: Promise<BlockedSearchParams>;
}) {
  const params = await searchParams;
  const deviceId = positiveInteger(params.device);
  const profileId = positiveInteger(params.profile);
  const hours = positiveInteger(params.hours) ?? 24 * 7;
  const page = positiveInteger(params.page) ?? 1;
  const [blocked, devices, profiles, domainRules] = await Promise.all([
    getBlockedRequests({
      deviceId,
      profileId,
      category: params.category || undefined,
      domain: params.domain?.trim() || undefined,
      hours,
      page,
      perPage: 50,
    }),
    getAllDevices({ sortBy: "name", sortOrder: "asc" }),
    getControlProfiles(),
    getDomainRules(),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Website Blocking
        </h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm">
          Apply real DNS rules and review requests blocked by the configured
          provider. NetWatch stores domain and policy metadata, never page
          contents or passwords.
        </p>
      </div>

      <Card>
        <CardContent className="pt-5">
          <GlobalRulesManager
            rules={domainRules.filter((rule) => rule.scope_type === "global")}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_1.3fr_auto_auto]">
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
            <NativeSelect
              name="profile"
              defaultValue={params.profile ?? ""}
              className="w-full"
            >
              <option value="">All profiles</option>
              {profiles.items.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect
              name="category"
              defaultValue={params.category ?? ""}
              className="w-full"
            >
              <option value="">All categories</option>
              {Object.entries(profiles.categories).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
            <Input
              name="domain"
              defaultValue={params.domain ?? ""}
              placeholder="Search domain"
              aria-label="Search domain"
              className="font-mono"
            />
            <NativeSelect name="hours" defaultValue={String(hours)}>
              <option value="24">24 hours</option>
              <option value="168">7 days</option>
              <option value="720">30 days</option>
              <option value="2160">90 days</option>
            </NativeSelect>
            <Button type="submit">
              <Search />
              Filter
            </Button>
          </form>
        </CardContent>
      </Card>

      {blocked.items.length ? (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Device</TableHead>
                  <TableHead>Domain</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Rule</TableHead>
                  <TableHead>Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {blocked.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell title={formatDate(item.timestamp)}>
                      {formatRelativeTime(item.timestamp)}
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/devices/${item.device_id}?tab=internet`}
                        className="hover:text-primary font-medium"
                      >
                        {item.device_name}
                      </Link>
                      {item.profile_name ? (
                        <span className="text-muted-foreground mt-1 block text-xs">
                          {item.profile_name}
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="min-w-56 font-mono text-xs">
                      <details>
                        <summary className="hover:text-primary cursor-pointer list-none">
                          {item.domain}
                        </summary>
                        <p className="text-muted-foreground mt-2 max-w-md font-sans text-xs leading-5">
                          {item.explanation}
                        </p>
                      </details>
                    </TableCell>
                    <TableCell>{item.category}</TableCell>
                    <TableCell className="text-muted-foreground text-xs">
                      {item.rule}
                    </TableCell>
                    <TableCell>
                      <Badge variant="warning">Blocked</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="border-border flex items-center justify-between border-t p-4 text-xs">
            <span className="text-muted-foreground">
              {blocked.total} blocked request{blocked.total === 1 ? "" : "s"}
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
                asChild={page < blocked.pages}
                disabled={page >= blocked.pages}
              >
                {page < blocked.pages ? (
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
          icon={Ban}
          title="No blocked requests"
          description="No matching DNS blocks were reported in this period. If you expect data, confirm that client DNS traffic is using the configured provider."
        />
      )}
    </div>
  );
}
