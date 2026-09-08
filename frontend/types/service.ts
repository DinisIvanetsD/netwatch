export interface DetectedService {
  id: number;
  device_id: number;
  device_name: string;
  ip_address: string;
  port: number;
  protocol: string;
  service_name: string;
  first_seen: string;
  last_seen: string;
  active: boolean;
}

export interface ServiceListResponse {
  items: DetectedService[];
  total: number;
}
