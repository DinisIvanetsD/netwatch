import { describe, expect, it } from "vitest";

import { escapeCsvCell, toCsv } from "@/lib/csv";

describe("toCsv", () => {
  it("escapes commas, quotes, and newlines", () => {
    expect(
      toCsv(
        [{ name: 'Kitchen, "hub"', note: "line one\nline two" }],
        [
          { key: "name", label: "Name" },
          { key: "note", label: "Note" },
        ],
      ),
    ).toBe('Name,Note\r\n"Kitchen, ""hub""","line one\nline two"\r\n');
  });

  it("keeps an empty report as a header-only CSV", () => {
    expect(toCsv([], [{ key: "name", label: "Name" }])).toBe("Name\r\n");
  });

  it("neutralizes spreadsheet formula prefixes", () => {
    expect(escapeCsvCell("=1+1")).toBe("'=1+1");
    expect(escapeCsvCell("+SUM(A1:A2)")).toBe("'+SUM(A1:A2)");
    expect(escapeCsvCell("-2+3")).toBe("'-2+3");
    expect(escapeCsvCell("@cmd")).toBe("'@cmd");
    expect(escapeCsvCell('\t=HYPERLINK("https://example.com")')).toBe(
      '"\'\t=HYPERLINK(""https://example.com"")"',
    );
  });
});
