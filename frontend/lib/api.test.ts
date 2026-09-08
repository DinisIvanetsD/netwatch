import { afterEach, describe, expect, it, vi } from "vitest";

import { getAllDevices } from "@/lib/api";

function device(id: number, ipAddress: string) {
  return {
    id,
    name: null,
    hostname: null,
    ip_address: ipAddress,
  };
}

function page(
  items: ReturnType<typeof device>[],
  number: number,
  pages: number,
) {
  return new Response(
    JSON.stringify({
      items,
      page: number,
      per_page: 100,
      total: 2,
      pages,
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

describe("getAllDevices", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads every device using API-compliant page sizes", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(page([device(1, "192.168.1.1")], 1, 2))
      .mockResolvedValueOnce(page([device(2, "192.168.1.2")], 2, 2));
    vi.stubGlobal("fetch", fetchMock);

    const devices = await getAllDevices({
      sortBy: "name",
      sortOrder: "asc",
    });

    expect(devices.map(({ id }) => id)).toEqual([1, 2]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0][0])).toContain("page=1&per_page=100");
    expect(String(fetchMock.mock.calls[1][0])).toContain("page=2&per_page=100");
  });
});
