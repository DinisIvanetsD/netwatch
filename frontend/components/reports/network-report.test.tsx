import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NetworkReport } from "@/components/reports/network-report";

describe("NetworkReport", () => {
  it("explains empty device and alert report sections", () => {
    render(
      <NetworkReport
        data={{ devices: [], alerts: [], dnsActivity: [], dnsAvailable: true }}
      />,
    );

    expect(
      screen.getByText("No devices are currently loaded."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No alerts are currently loaded."),
    ).toBeInTheDocument();
    expect(screen.getByText(/reports DNS metadata only/i)).toBeInTheDocument();
  });
});
