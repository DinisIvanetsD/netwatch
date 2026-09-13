export type NetWatchRuntimeConfig = {
  apiUrl: string;
  websocketUrl: string;
};

export const publicConfig: NetWatchRuntimeConfig = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  websocketUrl:
    process.env.NEXT_PUBLIC_WS_URL ??
    (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
      /^http/,
      "ws",
    ) + "/ws",
};

let runtimeConfigPromise: Promise<NetWatchRuntimeConfig> | null = null;

export function getRuntimeConfig(): Promise<NetWatchRuntimeConfig> {
  if (typeof window === "undefined") return Promise.resolve(publicConfig);
  if (runtimeConfigPromise) return runtimeConfigPromise;

  runtimeConfigPromise = fetch("/api/runtime-config", {
    cache: "no-store",
  })
    .then(async (response) => {
      if (!response.ok)
        throw new Error("Runtime configuration is unavailable.");
      const payload = (await response.json()) as Partial<NetWatchRuntimeConfig>;
      if (
        typeof payload.apiUrl !== "string" ||
        typeof payload.websocketUrl !== "string"
      ) {
        throw new Error("Runtime configuration is invalid.");
      }
      return payload as NetWatchRuntimeConfig;
    })
    .catch(() => publicConfig);

  return runtimeConfigPromise;
}
