export interface InternetActivityItem {
  id: number;
  device_id: number;
  device_name: string | null;
  profile_id: number | null;
  provider_id: string;
  timestamp: string;
  source_ip: string | null;
  destination_ip: string | null;
  domain: string;
  registered_domain: string | null;
  service: string | null;
  category: string;
  protocol: string | null;
  destination_port: number | null;
  bytes_sent: number | null;
  bytes_received: number | null;
  query_type: string | null;
  response_status: string;
  blocked: boolean;
  reason: string | null;
}

export interface InternetActivityList {
  items: InternetActivityItem[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
  visibility: "dns_metadata";
}

export interface InternetActivitySummary {
  total_queries: number;
  blocked_queries: number;
  active_devices: number;
  top_domains: Array<{ domain: string; count: number }>;
  top_services: Array<{ service: string; count: number }>;
  categories: Array<{ category: string; count: number }>;
  visibility: "dns_metadata";
}

export interface InternetActivityDiagnostics {
  status:
    | "ready"
    | "not_configured"
    | "provider_error"
    | "no_queries"
    | "unmatched_clients";
  provider_id: string;
  provider_name: string;
  provider_status: string;
  network_cidr: string;
  dns_port: number;
  records_checked: number;
  matched_records: number;
  matched_devices: number;
  unmatched_clients: string[];
  message: string;
  steps: string[];
}

export interface InternetActivityQuery {
  deviceId?: number;
  category?: string;
  blocked?: boolean;
  search?: string;
  hours?: number;
  page?: number;
  perPage?: number;
}
