export type ScanStatus =
  "pending" | "running" | "completed" | "failed" | "cancelled";

export interface Scan {
  id: number;
  started_at: string | null;
  finished_at: string | null;
  status: ScanStatus;
  devices_found: number;
  duration_ms: number | null;
  error: string | null;
  subnet: string;
  created_at: string;
}
