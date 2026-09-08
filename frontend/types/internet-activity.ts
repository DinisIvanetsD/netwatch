export interface InternetActivityItem {
  id: number;
  device_id: number;
  provider_id: string;
  timestamp: string;
  domain: string;
  category: string;
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
  categories: Array<{ category: string; count: number }>;
  visibility: "dns_metadata";
}
