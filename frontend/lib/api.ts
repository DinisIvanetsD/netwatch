import { publicConfig } from "@/lib/config";
import type { Device, DeviceListResponse, DeviceQuery } from "@/types/device";
import type { Scan } from "@/types/scan";
import type { ServiceListResponse } from "@/types/service";
import type { HistoryClearResult, NetWatchSettings } from "@/types/settings";
import type { NetworkActivity, NetworkStatus } from "@/types/network";
import type {
  InternetActivityDiagnostics,
  InternetActivityQuery,
  InternetActivityList,
  InternetActivitySummary,
} from "@/types/internet-activity";
import type { Alert, AlertListResponse } from "@/types/alert";
import type {
  AdGuardConfigurationInput,
  AdGuardIntegration,
  ProviderCapabilityList,
  ProviderStatus,
  SafeSearchConfiguration,
} from "@/types/integration";
import type {
  AccessAuditList,
  AccessOverview,
  AccessScheduleInput,
  BlockedRequestList,
  BlockedRequestQuery,
  ControlProfile,
  ControlProfileInput,
  ControlProfileList,
  DeviceControlAction,
  DeviceControlResult,
  DeviceIdentityInput,
  DomainRule,
  DomainRuleInput,
} from "@/types/control";
import type {
  EventListResponse,
  EventSeverity,
  EventType,
  MetricListResponse,
} from "@/types/history";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl =
    typeof window === "undefined"
      ? (process.env.NETWATCH_INTERNAL_API_URL ?? publicConfig.apiUrl)
      : publicConfig.apiUrl;
  const response = await fetch(`${apiUrl}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    ...init,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string | Array<{ msg?: string }>;
    } | null;
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail[0]?.msg
          ? detail[0].msg.replace(/^Value error, /, "")
          : `NetWatch API request failed with status ${response.status}.`;
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const jsonHeaders = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

export async function getDevices(
  query: DeviceQuery = {},
): Promise<DeviceListResponse> {
  const params = new URLSearchParams();
  if (query.page) params.set("page", String(query.page));
  if (query.perPage) params.set("per_page", String(query.perPage));
  if (query.status) params.set("status", query.status);
  if (query.search) params.set("search", query.search);
  if (query.sortBy) params.set("sort_by", query.sortBy);
  if (query.sortOrder) params.set("sort_order", query.sortOrder);

  const suffix = params.size ? `?${params.toString()}` : "";
  return request<DeviceListResponse>(`/api/devices${suffix}`);
}

export async function getAllDevices(
  query: Omit<DeviceQuery, "page" | "perPage"> = {},
): Promise<Device[]> {
  const firstPage = await getDevices({ ...query, page: 1, perPage: 100 });
  const items = [...firstPage.items];

  for (let page = 2; page <= firstPage.pages; page += 1) {
    const nextPage = await getDevices({ ...query, page, perPage: 100 });
    items.push(...nextPage.items);
  }

  return items;
}

export async function getDevice(deviceId: number): Promise<Device> {
  return request<Device>(`/api/devices/${deviceId}`);
}

export async function startScan(): Promise<Scan> {
  return request<Scan>("/api/scans", { method: "POST" });
}

export async function getScan(scanId: number): Promise<Scan> {
  return request<Scan>(`/api/scans/${scanId}`);
}

export async function getEvents(
  query: {
    deviceId?: number;
    severity?: EventSeverity;
    type?: EventType;
    perPage?: number;
    fromTime?: string;
    toTime?: string;
  } = {},
): Promise<EventListResponse> {
  const params = new URLSearchParams();
  if (query.deviceId) params.set("device_id", String(query.deviceId));
  if (query.severity) params.set("severity", query.severity);
  if (query.type) params.set("type", query.type);
  if (query.perPage) params.set("per_page", String(query.perPage));
  if (query.fromTime) params.set("from_time", query.fromTime);
  if (query.toTime) params.set("to_time", query.toTime);
  const suffix = params.size ? `?${params.toString()}` : "";
  return request<EventListResponse>(`/api/events${suffix}`);
}

export async function getDeviceMetrics(
  deviceId: number,
  perPage = 100,
): Promise<MetricListResponse> {
  return request<MetricListResponse>(
    `/api/devices/${deviceId}/metrics?per_page=${perPage}`,
  );
}

export async function getServices(): Promise<ServiceListResponse> {
  return request<ServiceListResponse>("/api/services");
}

export async function getDeviceServices(
  deviceId: number,
): Promise<ServiceListResponse> {
  return request<ServiceListResponse>(`/api/services/device/${deviceId}`);
}

export async function getSettings(): Promise<NetWatchSettings> {
  return request<NetWatchSettings>("/api/settings");
}

export async function updateSettings(
  payload: Partial<NetWatchSettings>,
): Promise<NetWatchSettings> {
  return request<NetWatchSettings>("/api/settings", {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export async function clearHistory(): Promise<HistoryClearResult> {
  return request<HistoryClearResult>("/api/settings/history", {
    method: "DELETE",
  });
}

export async function updateServiceSettings(payload: {
  service_scan_enabled: boolean;
  service_ports: number[];
}): Promise<NetWatchSettings> {
  return updateSettings(payload);
}

export async function getAlerts(): Promise<AlertListResponse> {
  return request<AlertListResponse>("/api/alerts");
}
export async function updateAlert(
  alertId: number,
  payload: { read?: boolean; resolved?: boolean },
): Promise<Alert> {
  return request<Alert>(`/api/alerts/${alertId}`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}
export async function updateAlertSettings(
  payload: Record<string, boolean>,
): Promise<NetWatchSettings> {
  return updateSettings(payload);
}

export async function getNetworkStatus(): Promise<NetworkStatus> {
  return request<NetworkStatus>("/api/network/status");
}

export async function getNetworkActivity(hours = 24): Promise<NetworkActivity> {
  return request<NetworkActivity>(`/api/network/activity?hours=${hours}`);
}

export async function getAdGuardConfiguration(): Promise<AdGuardIntegration | null> {
  try {
    return await request<AdGuardIntegration>("/api/integrations/adguard");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function configureAdGuard(
  payload: AdGuardConfigurationInput,
): Promise<AdGuardIntegration> {
  return request<AdGuardIntegration>("/api/integrations/adguard", {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export async function testAdGuard(payload: {
  server_url: string;
  username: string;
  password?: string;
}): Promise<{
  status: ProviderStatus;
  message: string;
  version: string | null;
}> {
  return request("/api/integrations/adguard/test", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export async function getInternetActivity(
  input: InternetActivityQuery | number = {},
): Promise<InternetActivityList> {
  const query = typeof input === "number" ? { deviceId: input } : input;
  const params = new URLSearchParams();
  if (query.deviceId) params.set("device_id", String(query.deviceId));
  if (query.category) params.set("category", query.category);
  if (query.blocked !== undefined) params.set("blocked", String(query.blocked));
  if (query.search) params.set("search", query.search);
  if (query.hours) params.set("hours", String(query.hours));
  if (query.page) params.set("page", String(query.page));
  if (query.perPage) params.set("per_page", String(query.perPage));
  const suffix = params.size ? `?${params.toString()}` : "";
  return request<InternetActivityList>(`/api/internet-activity${suffix}`);
}

export async function getInternetActivitySummary(
  deviceId?: number,
  hours = 24,
): Promise<InternetActivitySummary> {
  const params = new URLSearchParams({ hours: String(hours) });
  if (deviceId) params.set("device_id", String(deviceId));
  return request<InternetActivitySummary>(
    `/api/internet-activity/summary?${params.toString()}`,
  );
}

export async function getInternetActivityDiagnostics(): Promise<InternetActivityDiagnostics> {
  return request<InternetActivityDiagnostics>(
    "/api/internet-activity/diagnostics",
  );
}

export async function getProviderCapabilities(): Promise<ProviderCapabilityList> {
  return request<ProviderCapabilityList>("/api/integrations/capabilities");
}

export async function getSafeSearch(): Promise<SafeSearchConfiguration> {
  return request<SafeSearchConfiguration>("/api/integrations/dns/safe-search");
}

export async function updateSafeSearch(
  payload: SafeSearchConfiguration,
): Promise<SafeSearchConfiguration> {
  return request<SafeSearchConfiguration>("/api/integrations/dns/safe-search", {
    method: "PUT",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export async function getControlProfiles(): Promise<ControlProfileList> {
  return request<ControlProfileList>("/api/parental/profiles");
}

export async function createControlProfile(
  payload: ControlProfileInput,
): Promise<ControlProfile> {
  return request<ControlProfile>("/api/parental/profiles", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export async function updateControlProfile(
  profileId: number,
  payload: Partial<ControlProfileInput>,
): Promise<ControlProfile> {
  return request<ControlProfile>(`/api/parental/profiles/${profileId}`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export async function deleteControlProfile(profileId: number): Promise<void> {
  return request<void>(`/api/parental/profiles/${profileId}`, {
    method: "DELETE",
  });
}

export async function assignProfileDevices(
  profileId: number,
  deviceIds: number[],
): Promise<ControlProfile> {
  return request<ControlProfile>(
    `/api/parental/profiles/${profileId}/devices`,
    {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify({ device_ids: deviceIds }),
    },
  );
}

export async function replaceProfileSchedules(
  profileId: number,
  schedules: AccessScheduleInput[],
): Promise<ControlProfile> {
  return request<ControlProfile>(
    `/api/parental/profiles/${profileId}/schedules`,
    {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify({ schedules }),
    },
  );
}

export async function getDomainRules(): Promise<DomainRule[]> {
  return request<DomainRule[]>("/api/parental/domain-rules");
}

export async function createDomainRule(
  payload: DomainRuleInput,
): Promise<DomainRule> {
  return request<DomainRule>("/api/parental/domain-rules", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export async function retryDomainRule(ruleId: number): Promise<DomainRule> {
  return request<DomainRule>(`/api/parental/domain-rules/${ruleId}/retry`, {
    method: "POST",
  });
}

export async function deleteDomainRule(ruleId: number): Promise<void> {
  return request<void>(`/api/parental/domain-rules/${ruleId}`, {
    method: "DELETE",
  });
}

export async function getAccessOverview(): Promise<AccessOverview> {
  return request<AccessOverview>("/api/access-control");
}

export async function getAccessAudit(
  deviceId?: number,
  page = 1,
): Promise<AccessAuditList> {
  const params = new URLSearchParams({ page: String(page), per_page: "50" });
  if (deviceId) params.set("device_id", String(deviceId));
  return request<AccessAuditList>(`/api/access-audit?${params.toString()}`);
}

export async function updateDeviceIdentity(
  deviceId: number,
  payload: DeviceIdentityInput,
): Promise<Device> {
  return request<Device>(`/api/devices/${deviceId}/identity`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export async function runDeviceControlAction(
  deviceId: number,
  action: DeviceControlAction,
  durationMinutes?: number,
): Promise<DeviceControlResult> {
  const body =
    action === "pause-internet"
      ? JSON.stringify({ duration_minutes: durationMinutes ?? null })
      : undefined;
  return request<DeviceControlResult>(`/api/devices/${deviceId}/${action}`, {
    method: "POST",
    ...(body ? { headers: jsonHeaders, body } : {}),
  });
}

export async function getBlockedRequests(
  query: BlockedRequestQuery = {},
): Promise<BlockedRequestList> {
  const params = new URLSearchParams();
  if (query.deviceId) params.set("device_id", String(query.deviceId));
  if (query.profileId) params.set("profile_id", String(query.profileId));
  if (query.category) params.set("category", query.category);
  if (query.domain) params.set("domain", query.domain);
  if (query.hours) params.set("hours", String(query.hours));
  if (query.page) params.set("page", String(query.page));
  if (query.perPage) params.set("per_page", String(query.perPage));
  const suffix = params.size ? `?${params.toString()}` : "";
  return request<BlockedRequestList>(`/api/blocked-requests${suffix}`);
}
