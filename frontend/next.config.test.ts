import { describe, expect, it } from "vitest";

import nextConfig from "./next.config";

describe("metadata rendering", () => {
  it.each([
    "Mozilla/5.0 Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 Firefox/140.0",
    "Googlebot",
    "",
  ])("uses blocking metadata for user agent %j", (userAgent) => {
    expect(nextConfig.htmlLimitedBots?.test(userAgent)).toBe(true);
  });

  it("keeps React strict mode enabled", () => {
    expect(nextConfig.reactStrictMode).toBe(true);
  });
});
