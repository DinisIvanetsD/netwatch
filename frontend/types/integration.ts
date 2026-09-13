export type ProviderStatus =
  | "not_configured"
  | "connected"
  | "disconnected"
  | "authentication_failed"
  | "rate_limited"
  | "unsupported_version"
  | "error";

export interface TechnitiumIntegration {
  provider_id: "technitium_dns";
  display_name: string;
  kind: "dns";
  enabled: boolean;
  server_url: string;
  username: string;
  dns_port: number;
  password_set: boolean;
  status: ProviderStatus;
  message: string;
  version: string | null;
}

export interface TechnitiumConfigurationInput {
  server_url: string;
  username: string;
  password?: string;
  dns_port: number;
  enabled: boolean;
}

export type RouterProviderId =
  "openwrt" | "opnsense" | "generic" | "nos" | "hitron";

export interface RouterIntegration {
  provider_id: RouterProviderId | string;
  display_name: string;
  kind: "network";
  enabled: boolean;
  server_url: string;
  credential_set: boolean;
  status: ProviderStatus;
  message: string;
  version: string | null;
}

export interface RouterConfigurationInput {
  provider_id: RouterProviderId;
  server_url: string;
  username?: string;
  password?: string;
  api_key?: string;
  api_secret?: string;
  enabled: boolean;
  confirm_state_changes: boolean;
}

export type ProviderKind = "dns" | "network";

export interface ProviderCapability {
  provider_id: string;
  display_name: string;
  kind: ProviderKind;
  configured: boolean;
  status: ProviderStatus;
  message: string;
  version: string | null;
  capabilities: Record<string, boolean>;
}

export interface ProviderCapabilityList {
  items: ProviderCapability[];
}

export interface SafeSearchConfiguration {
  enabled: boolean;
  google: boolean;
  bing: boolean;
  youtube: boolean;
  duckduckgo: boolean;
  ecosia: boolean;
  pixabay: boolean;
  yandex: boolean;
}
