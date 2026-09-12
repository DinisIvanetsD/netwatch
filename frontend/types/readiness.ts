export type ReadinessStatus =
  "ready" | "degraded" | "unavailable" | "not_configured" | "unsupported";

export interface ReadinessCheck {
  status: ReadinessStatus;
  message: string;
}

export interface ReadinessResponse {
  status: "ready" | "degraded";
  checks: Record<string, ReadinessCheck>;
}
