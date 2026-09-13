import { describe, expect, it } from "vitest";

import { deviceDisplayLabel, hasAssignedDeviceName } from "@/lib/format";

describe("hasAssignedDeviceName", () => {
  it("does not treat an automatically discovered hostname as an assigned name", () => {
    expect(
      hasAssignedDeviceName({
        name: "DESKTOP-DINIS",
        hostname: "DESKTOP-DINIS",
        ip_address: "192.168.1.37",
      }),
    ).toBe(false);
  });

  it("recognizes a name different from discovery evidence as assigned", () => {
    expect(
      hasAssignedDeviceName({
        name: "Dinis laptop",
        hostname: "DESKTOP-DINIS",
        ip_address: "192.168.1.37",
      }),
    ).toBe(true);
  });

  it("keeps unassigned device labels distinguishable with their IP", () => {
    expect(
      deviceDisplayLabel({
        name: "",
        hostname: null,
        ip_address: "192.168.1.131",
      }),
    ).toBe("Unnamed device · 192.168.1.131");
  });
});
