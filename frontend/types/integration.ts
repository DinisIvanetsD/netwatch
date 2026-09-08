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
