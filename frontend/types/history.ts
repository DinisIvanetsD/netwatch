export type EventSeverity = "info" | "low" | "medium" | "high";

export type EventType =
  | "device.discovered"
  | "device.online"
  | "device.offline"
  | "device.updated"
  | "device.latency_increased"
  | "service.discovered"
  | "service.removed";

export interface NetworkEvent {
  id: number;
  device_id: number | null;
  device_name: string | null;
  type: EventType;
  message: string;
  severity: EventSeverity;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface DeviceMetric {
  id: number;
  device_id: number;
  timestamp: string;
  latency_ms: number | null;
  online: boolean;
}

export interface EventListResponse {
  items: NetworkEvent[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
}

export interface MetricListResponse {
  items: DeviceMetric[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
}
