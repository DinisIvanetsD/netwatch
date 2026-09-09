export type DeviceStatus = "online" | "offline" | "new" | "unknown";
export type DeviceTrustState =
  "trusted" | "unknown" | "quarantined" | "blocked" | "ignored";
export type InternetAccessState = "allowed" | "paused" | "blocked";

export interface Device {
  id: number;
  name: string | null;
  ip_address: string;
  network_cidr: string;
  mac_address: string | null;
  hostname: string | null;
  vendor: string | null;
  status: DeviceStatus;
  latency_ms: number | null;
  first_seen: string;
  last_seen: string;
  created_at: string;
  updated_at: string;
  is_gateway: boolean;
  device_type: string | null;
  owner: string | null;
  profile_id: number | null;
  trust_state: DeviceTrustState;
  internet_access: InternetAccessState;
  lan_access: string;
  paused_until: string | null;
  quarantine_reason: string | null;
  quarantined_at: string | null;
  service_ports: number[];
}

export interface DeviceListResponse {
  items: Device[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
}

export interface DeviceQuery {
  page?: number;
  perPage?: number;
  status?: DeviceStatus;
  search?: string;
  sortBy?: "name" | "ip_address" | "status" | "latency_ms" | "last_seen";
  sortOrder?: "asc" | "desc";
}
