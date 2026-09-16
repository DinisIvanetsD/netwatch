import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccessPolicyForm } from "@/components/settings/access-policy-form";
import type { NetWatchSettings } from "@/types/settings";

const mocks = vi.hoisted(() => ({ updateSettings: vi.fn() }));
vi.mock("@/lib/api", () => ({ updateSettings: mocks.updateSettings }));

const initial: NetWatchSettings = {
  subnet: "192.168.1.0/24",
  auto_detect_network: false,
  scan_interval: 60,
  scan_concurrency: 32,
  monitoring_enabled: true,
  service_scan_enabled: true,
  service_ports: [22, 53, 80, 443, 445, 3389],
  offline_after_missed_scans: 3,
  new_device_alerts: true,
  new_device_policy: "allow_alert",
  device_offline_alerts: true,
  new_service_alerts: true,
  latency_alerts: true,
  retention_days: 30,
  operating_mode: "live",
};

describe("AccessPolicyForm", () => {
  it("warns when router enforcement is unavailable and saves the policy", async () => {
    mocks.updateSettings.mockResolvedValue({
      ...initial,
      new_device_policy: "quarantine_alert",
    });
    render(
      <AccessPolicyForm initial={initial} routerControlAvailable={false} />,
    );

    fireEvent.change(screen.getByLabelText("New device policy"), {
      target: { value: "quarantine_alert" },
    });
    expect(
      screen.getByText(/automatic network enforcement cannot run/i),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save access policy" }));

    await waitFor(() =>
      expect(mocks.updateSettings).toHaveBeenCalledWith({
        new_device_policy: "quarantine_alert",
      }),
    );
  });
});
