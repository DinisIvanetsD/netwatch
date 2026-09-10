import type { Device, DeviceTrustState } from "@/types/device";
import type { ProviderStatus } from "@/types/integration";

export type RuleScope = "global" | "profile" | "device";
export type RuleAction = "allow" | "block";

export interface DomainRule {
  id: number;
  scope_type: RuleScope;
  scope_id: number | null;
  domain: string;
  action: RuleAction;
  include_subdomains: boolean;
  reason: string | null;
  enabled: boolean;
  expires_at: string | null;
  enforcement_status: "pending" | "active" | "error" | "expired" | "demo";
  enforcement_error: string | null;
  last_applied_at: string | null;
  created_at: string;
}

export interface DomainRuleInput {
  scope_type: RuleScope;
  scope_id: number | null;
  domain: string;
  action: RuleAction;
  include_subdomains: boolean;
  reason?: string;
  expires_at?: string;
}

export interface AccessSchedule {
  id: number;
  profile_id: number;
  weekday: number;
  start_minute: number;
  end_minute: number;
  enabled: boolean;
}

export interface AccessScheduleInput {
  weekday: number;
  start_minute: number;
  end_minute: number;
  enabled: boolean;
}

export interface ControlProfile {
  id: number;
  name: string;
  description: string | null;
  internet_enabled: boolean;
  safe_search_enabled: boolean;
  blocked_categories: string[];
  created_at: string;
  updated_at: string;
  device_ids: number[];
  device_count: number;
  blocked_requests_today: number;
  schedules: AccessSchedule[];
  domain_rules: DomainRule[];
  schedule_state:
    | "allowed"
    | "allowed_by_schedule"
    | "blocked_by_schedule"
    | "blocked_by_profile";
  next_schedule_change: string | null;
}

export interface ControlProfileList {
  items: ControlProfile[];
  categories: Record<string, string>;
}

export interface ControlProfileInput {
  name: string;
  description?: string | null;
  internet_enabled: boolean;
  safe_search_enabled: boolean;
  blocked_categories: string[];
}

export interface AccessOverview {
  devices: Device[];
  trusted: number;
  unknown: number;
  quarantined: number;
  blocked: number;
  ignored: number;
  provider_id: string;
  provider_name: string;
  provider_configured: boolean;
  provider_status: ProviderStatus;
  capabilities: Record<string, boolean>;
  message: string;
}

export interface DeviceIdentityInput {
  name?: string | null;
  device_type?: string | null;
  owner?: string | null;
  profile_id?: number | null;
  is_gateway?: boolean;
}

export type DeviceControlAction =
  | "trust"
  | "ignore"
  | "pause-internet"
  | "resume-internet"
  | "block-internet"
  | "quarantine"
  | "release"
  | "block";

export interface DeviceControlResult {
  changed: boolean;
  message: string;
  device: Device;
}

export interface AccessAudit {
  id: number;
  device_id: number | null;
  device_name: string | null;
  action: string;
  actor: string;
  result: string;
  provider_id: string | null;
  message: string;
  expires_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AccessAuditList {
  items: AccessAudit[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface BlockedRequest {
  id: number;
  device_id: number;
  device_name: string;
  profile_id: number | null;
  profile_name: string | null;
  timestamp: string;
  domain: string;
  registered_domain: string | null;
  service: string | null;
  category: string;
  rule: string;
  provider_id: string;
  explanation: string;
}

export interface BlockedRequestList {
  items: BlockedRequest[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface BlockedRequestQuery {
  deviceId?: number;
  profileId?: number;
  category?: string;
  domain?: string;
  hours?: number;
  page?: number;
  perPage?: number;
}

export const trustStateLabels: Record<DeviceTrustState, string> = {
  trusted: "Trusted",
  unknown: "Unknown",
  quarantined: "Quarantined",
  blocked: "Blocked",
  ignored: "Ignored",
};
