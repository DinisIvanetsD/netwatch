export interface NetworkStatus {
  subnet: string;
  network_id: string;
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

export interface NetworkProfile {
  subnet: string;
  network_id: string;
  label: string;
  is_current: boolean;
  devices_known: number;
  scan_count: number;
  last_seen: string | null;
}

export interface NetworkProfileList {
  items: NetworkProfile[];
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

export interface NetworkHistoryItem {
  device_id: number;
  sample_count: number;
  online_samples: number;
  average_latency_ms: number | null;
  last_sample_at: string | null;
}

export interface NetworkHistory {
  hours: number;
  items: NetworkHistoryItem[];
}
