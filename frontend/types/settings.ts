export interface NetWatchSettings {
  subnet: string;
  scan_interval: number;
  scan_concurrency: number;
  monitoring_enabled: boolean;
  service_scan_enabled: boolean;
  service_ports: number[];
  offline_after_missed_scans: number;
  new_device_alerts: boolean;
  device_offline_alerts: boolean;
  new_service_alerts: boolean;
  latency_alerts: boolean;
}
