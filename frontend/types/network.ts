export interface NetworkStatus {
  subnet: string;
  gateway: string | null;
  dns_servers: string[];
  interface_name: string | null;
  local_ip: string | null;
  discovery_mode: "windows_sensor" | "container";
  auto_detect_network: boolean;
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
