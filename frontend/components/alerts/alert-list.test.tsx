import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AlertList } from "@/components/alerts/alert-list";
import type { Alert } from "@/types/alert";

const mocks = vi.hoisted(() => ({ updateAlert: vi.fn() }));
vi.mock("@/lib/api", () => ({ updateAlert: mocks.updateAlert }));

const alerts: Alert[] = [
  {
    id: 1,
    device_id: 1,
    device_name: "Living Room TV",
    type: "device.offline",
    severity: "medium",
    title: "Device offline",
    description: "Living Room TV went offline.",
    created_at: "2026-09-08T20:00:00Z",
    read: false,
    resolved: false,
    resolved_at: null,
  },
  {
    id: 2,
    device_id: 2,
    device_name: "Laptop",
    type: "service.discovered",
    severity: "low",
    title: "New service detected",
    description: "TCP 443 / HTTPS was newly observed.",
    created_at: "2026-09-08T19:00:00Z",
    read: true,
    resolved: true,
    resolved_at: "2026-09-08T19:30:00Z",
  },
];

describe("AlertList", () => {
  beforeEach(() => vi.clearAllMocks());

  it("filters alerts by search, severity and unresolved status", () => {
    render(<AlertList initial={alerts} />);

    fireEvent.change(screen.getByPlaceholderText("Search alerts or devices"), {
      target: { value: "Living Room" },
    });
    fireEvent.change(screen.getByLabelText("Filter by severity"), {
      target: { value: "medium" },
    });
    fireEvent.click(screen.getByLabelText("Unresolved only"));

    expect(screen.getByText("Device offline")).toBeInTheDocument();
    expect(screen.queryByText("New service detected")).not.toBeInTheDocument();
    expect(screen.getByText("Incident evidence")).toBeInTheDocument();
    expect(screen.getByText("Signal: device.offline")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Living Room TV" }),
    ).toHaveAttribute("href", "/devices/1?tab=activity");
  });

  it("updates an alert and reflects the resolved state", async () => {
    mocks.updateAlert.mockResolvedValue({
      ...alerts[0],
      read: true,
      resolved: true,
      resolved_at: "2026-09-08T21:00:00Z",
    });
    render(<AlertList initial={[alerts[0]]} />);

    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));

    await waitFor(() =>
      expect(mocks.updateAlert).toHaveBeenCalledWith(1, {
        resolved: true,
        read: true,
      }),
    );
    expect(await screen.findByText("Resolved")).toBeInTheDocument();
  });
});
