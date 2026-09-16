import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OperatingModeForm } from "@/components/settings/operating-mode-form";
import type { NetWatchSettings } from "@/types/settings";

const mocks = vi.hoisted(() => ({
  refresh: vi.fn(),
  updateSettings: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: mocks.refresh }),
}));
vi.mock("@/lib/api", () => ({ updateSettings: mocks.updateSettings }));

const initial: NetWatchSettings = {
  subnet: "192.168.1.0/24",
  auto_detect_network: false,
  scan_interval: 60,
  scan_concurrency: 32,
  monitoring_enabled: true,
  service_scan_enabled: true,
  service_ports: [22, 80, 443],
  offline_after_missed_scans: 3,
  new_device_alerts: true,
  new_device_policy: "allow_alert",
  device_offline_alerts: true,
  new_service_alerts: true,
  latency_alerts: true,
  retention_days: 30,
  operating_mode: "simulation",
};

describe("OperatingModeForm", () => {
  it("switches from simulation to the live sensor mode", async () => {
    mocks.updateSettings.mockResolvedValue({
      ...initial,
      operating_mode: "live",
    });
    render(<OperatingModeForm initial={initial} discoveryMode="container" />);

    fireEvent.click(screen.getByRole("radio", { name: /Live sensor/i }));

    await waitFor(() =>
      expect(mocks.updateSettings).toHaveBeenCalledWith({
        operating_mode: "live",
      }),
    );
    expect(
      await screen.findByText(/Live sensor mode is active/i),
    ).toBeInTheDocument();
  });

  it("restores the previous mode when the switch fails", async () => {
    mocks.updateSettings.mockRejectedValue(
      new Error("A scan is already running."),
    );
    render(
      <OperatingModeForm initial={initial} discoveryMode="windows_sensor" />,
    );

    fireEvent.click(screen.getByRole("radio", { name: /Live sensor/i }));

    await waitFor(() =>
      expect(mocks.updateSettings).toHaveBeenCalledWith({
        operating_mode: "live",
      }),
    );
    expect(screen.getByRole("radio", { name: /Simulation/i })).toBeChecked();
    expect(screen.getByText("A scan is already running.")).toBeInTheDocument();
  });
});
