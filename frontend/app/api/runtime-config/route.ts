function websocketUrl(apiUrl: string): string {
  return apiUrl.replace(/^http/i, "ws") + "/ws";
}

export const dynamic = "force-dynamic";

export function GET() {
  const apiUrl =
    process.env.NETWATCH_INTERNAL_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";
  const configuredWebsocketUrl =
    process.env.NETWATCH_INTERNAL_WS_URL ?? process.env.NEXT_PUBLIC_WS_URL;

  return Response.json(
    {
      apiUrl,
      websocketUrl: configuredWebsocketUrl ?? websocketUrl(apiUrl),
    },
    {
      headers: { "Cache-Control": "no-store" },
    },
  );
}
