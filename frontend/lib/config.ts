export const publicConfig = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  websocketUrl:
    process.env.NEXT_PUBLIC_WS_URL ??
    (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
      /^http/,
      "ws",
    ) + "/ws",
} as const;
