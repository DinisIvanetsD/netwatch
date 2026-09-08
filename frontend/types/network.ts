export interface NetworkStatus {
  subnet: string;
  gateway: string | null;
  dns_servers: string[];
  total_devices: number;
  online_devices: number;
  average_latency_ms: number | null;
  scan_running: boolean;
  last_completed_scan: string | null;
  next_scheduled_scan: string | null;
}

export interface NetworkActivityPoint {
  timestamp: string;
  online_devices: number;
  average_latency_ms: number | null;
  events: number;
}

export interface NetworkActivity {
  hours: number;
  points: NetworkActivityPoint[];
}
