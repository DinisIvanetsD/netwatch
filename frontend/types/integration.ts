export type ProviderStatus =
  | "not_configured"
  | "connected"
  | "disconnected"
  | "authentication_failed"
  | "unsupported_version"
  | "error";

export interface AdGuardIntegration {
  provider_id: "adguard_home";
  display_name: string;
  kind: "dns";
  enabled: boolean;
  server_url: string;
  username: string;
  password_set: boolean;
  status: ProviderStatus;
  message: string;
  version: string | null;
}

export interface AdGuardConfigurationInput {
  server_url: string;
  username: string;
  password?: string;
  enabled: boolean;
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
