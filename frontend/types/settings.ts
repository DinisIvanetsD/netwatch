export interface NetWatchSettings {
  subnet: string;
  auto_detect_network: boolean;
  scan_interval: number;
  scan_concurrency: number;
  monitoring_enabled: boolean;
  service_scan_enabled: boolean;
  service_ports: number[];
  offline_after_missed_scans: number;
  new_device_alerts: boolean;
  new_device_policy:
    "allow" | "allow_alert" | "quarantine_alert" | "block_alert";
  device_offline_alerts: boolean;
  new_service_alerts: boolean;
  latency_alerts: boolean;
  retention_days: number;
}

export interface HistoryClearResult {
  metrics_deleted: number;
  events_deleted: number;
  alerts_deleted: number;
  scans_deleted: number;
  internet_activity_deleted: number;
}
