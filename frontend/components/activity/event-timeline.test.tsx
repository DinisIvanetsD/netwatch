import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EventTimeline } from "@/components/activity/event-timeline";
import type { NetworkEvent } from "@/types/history";

const event: NetworkEvent = {
  id: 1,
  device_id: 7,
  device_name: "Kitchen speaker",
  type: "device.offline",
  message: "Kitchen speaker went offline",
  severity: "medium",
  timestamp: "2026-09-08T20:00:00Z",
  metadata: { source: "router telemetry", confidence: "medium" },
};

describe("EventTimeline", () => {
  it("shows severity, evidence context, and a device activity link", () => {
    render(<EventTimeline events={[event]} />);

    expect(screen.getAllByText("medium")).toHaveLength(2);
    expect(screen.getByText("Event evidence")).toBeInTheDocument();
    expect(screen.getByText("router telemetry")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Kitchen speaker" }),
    ).toHaveAttribute("href", "/devices/7?tab=activity");
  });
});
