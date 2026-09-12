import Link from "next/link";
import { Search } from "lucide-react";

import { DeviceTable } from "@/components/devices/device-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getDevices } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DeviceQuery, DeviceStatus } from "@/types/device";

export const metadata = { title: "Devices" };
export const dynamic = "force-dynamic";

type SearchParams = Promise<{
  page?: string;
  search?: string;
  status?: string;
  sort_by?: string;
  sort_order?: string;
}>;

const statuses: Array<{ label: string; value?: DeviceStatus }> = [
  { label: "All" },
  { label: "Online", value: "online" },
  { label: "Offline", value: "offline" },
  { label: "New", value: "new" },
  { label: "Unknown", value: "unknown" },
];

const sortFields = new Set<NonNullable<DeviceQuery["sortBy"]>>([
  "name",
  "ip_address",
  "status",
  "latency_ms",
  "last_seen",
]);

function filterUrl(
  current: Record<string, string | undefined>,
  status?: DeviceStatus,
) {
  const params = new URLSearchParams();
  if (current.search) params.set("search", current.search);
  if (current.sort_by) params.set("sort_by", current.sort_by);
  if (current.sort_order) params.set("sort_order", current.sort_order);
  if (status) params.set("status", status);
  const query = params.toString();
  return query ? `/devices?${query}` : "/devices";
}

function pageUrl(current: Record<string, string | undefined>, page: number) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(current)) {
    if (value && key !== "page") params.set(key, value);
  }
  params.set("page", String(page));
  return `/devices?${params.toString()}`;
}

export default async function DevicesPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const current = await searchParams;
  const parsedPage = Number.parseInt(current.page ?? "1", 10);
  const page = Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  const status = statuses.some((item) => item.value === current.status)
    ? (current.status as DeviceStatus)
    : undefined;
  const sortBy = sortFields.has(
    current.sort_by as NonNullable<DeviceQuery["sortBy"]>,
  )
    ? (current.sort_by as NonNullable<DeviceQuery["sortBy"]>)
    : "last_seen";
  const sortOrder = current.sort_order === "asc" ? "asc" : "desc";
  const search = current.search?.trim() || undefined;

  const data = await getDevices({
    page,
    perPage: 25,
    status,
    search,
    sortBy,
    sortOrder,
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Devices</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Inventory and inspect devices discovered on the authorized network.
          </p>
        </div>
        <p className="text-muted-foreground font-mono text-xs">
          {data.total} {data.total === 1 ? "device" : "devices"}
        </p>
      </div>

      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <nav
          className="border-border bg-card flex flex-wrap gap-1 rounded-lg border p-1"
          aria-label="Filter devices by status"
        >
          {statuses.map((item) => {
            const active = status === item.value || (!status && !item.value);
            return (
              <Link
                key={item.label}
                href={filterUrl(current, item.value)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  active
                    ? "bg-accent text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
                aria-current={active ? "page" : undefined}
                aria-label={`Show ${item.label.toLowerCase()} devices`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <form
          action="/devices"
          method="get"
          className="flex w-full gap-2 xl:max-w-md"
        >
          {status ? <input type="hidden" name="status" value={status} /> : null}
          <div className="relative flex-1">
            <Search className="text-muted-foreground pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2" />
            <Input
              name="search"
              defaultValue={search}
              placeholder="Search name, owner, hostname, IP or MAC"
              className="ps-9"
              aria-label="Search devices"
            />
          </div>
          <Button type="submit" variant="outline">
            Search
          </Button>
          {search ? (
            <Button variant="ghost" asChild>
              <Link href={filterUrl({}, status)}>Clear</Link>
            </Button>
          ) : null}
        </form>
      </div>

      <DeviceTable
        devices={data.items}
        sortBy={sortBy}
        sortOrder={sortOrder}
        query={current}
        filtered={Boolean(status || search)}
      />

      {data.pages > 1 ? (
        <nav
          className="flex items-center justify-between"
          aria-label="Device list pagination"
        >
          <p className="text-muted-foreground text-xs">
            Page {data.page} of {data.pages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              asChild={data.page > 1}
              disabled={data.page <= 1}
            >
              {data.page > 1 ? (
                <Link href={pageUrl(current, data.page - 1)}>Previous</Link>
              ) : (
                <span>Previous</span>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              asChild={data.page < data.pages}
              disabled={data.page >= data.pages}
            >
              {data.page < data.pages ? (
                <Link href={pageUrl(current, data.page + 1)}>Next</Link>
              ) : (
                <span>Next</span>
              )}
            </Button>
          </div>
        </nav>
      ) : null}
    </div>
  );
}
