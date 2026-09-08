import type { EventSeverity } from "@/types/history";
export interface Alert {
  id: number;
  device_id: number | null;
  device_name: string | null;
  type: string;
  severity: EventSeverity;
  title: string;
  description: string;
  created_at: string;
  read: boolean;
  resolved: boolean;
  resolved_at: string | null;
}
export interface AlertListResponse {
  items: Alert[];
  total: number;
}
