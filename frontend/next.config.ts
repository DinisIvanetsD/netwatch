import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  agentRules: false,
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // Keep metadata blocking for all user agents. This avoids the streamed
  // MetadataWrapper implicated in hydration mismatches across console routes.
  // Page rendering and WebSocket updates remain enabled.
  htmlLimitedBots: /.*/,
};

export default nextConfig;
