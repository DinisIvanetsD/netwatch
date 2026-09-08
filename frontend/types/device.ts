export type DeviceStatus = "online" | "offline" | "new" | "unknown";

export interface Device {
  id: number;
  name: string | null;
  ip_address: string;
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
