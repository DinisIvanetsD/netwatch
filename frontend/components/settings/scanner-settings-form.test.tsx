import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ScannerSettingsForm } from "@/components/settings/scanner-settings-form";
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
};

describe("ScannerSettingsForm", () => {
  it("saves an authorized subnet and scanner controls", async () => {
    mocks.updateSettings.mockResolvedValue({
      ...initial,
      subnet: "10.42.0.0/24",
    });
    render(<ScannerSettingsForm initial={initial} />);

    fireEvent.change(screen.getByLabelText("Monitored subnet"), {
      target: { value: "10.42.0.0/24" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save network settings" }),
    );

    await waitFor(() =>
      expect(mocks.updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          subnet: "10.42.0.0/24",
          auto_detect_network: false,
          scan_interval: 60,
          scan_concurrency: 32,
        }),
      ),
    );
    expect(
      await screen.findByText("Network and scanner settings saved."),
    ).toBeInTheDocument();
  });
});
