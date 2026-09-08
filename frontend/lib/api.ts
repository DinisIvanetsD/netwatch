import { publicConfig } from "@/lib/config";
import type { Device, DeviceListResponse, DeviceQuery } from "@/types/device";
import type { Scan } from "@/types/scan";
import type { ServiceListResponse } from "@/types/service";
import type { NetWatchSettings } from "@/types/settings";
import type { NetworkActivity, NetworkStatus } from "@/types/network";
import type { Alert, AlertListResponse } from "@/types/alert";
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
  const response = await fetch(`${publicConfig.apiUrl}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    ...init,
  });

  if (!response.ok) {
    throw new ApiError(
      `NetWatch API request failed with status ${response.status}.`,
      response.status,
    );
  }

  return (await response.json()) as T;
}

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

export async function updateServiceSettings(payload: {
  service_scan_enabled: boolean;
  service_ports: number[];
}): Promise<NetWatchSettings> {
  return request<NetWatchSettings>("/api/settings", {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
export async function updateAlertSettings(
  payload: Record<string, boolean>,
): Promise<NetWatchSettings> {
  return request<NetWatchSettings>("/api/settings", {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getNetworkStatus(): Promise<NetworkStatus> {
  return request<NetworkStatus>("/api/network/status");
}

export async function getNetworkActivity(hours = 24): Promise<NetworkActivity> {
  return request<NetworkActivity>(`/api/network/activity?hours=${hours}`);
}
