import { describe, expect, it } from "vitest";

import { describeService } from "@/lib/service-descriptions";

describe("describeService", () => {
  it("explains known and custom services without calling an open port a vulnerability", () => {
    expect(describeService("SSH", 22)).toMatch(/remote command-line/i);
    expect(describeService("TCP 9000", 9000)).toMatch(
      /not automatically a vulnerability/i,
    );
  });
});
