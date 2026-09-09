import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DeviceAccessPanel } from "@/components/control/device-access-panel";
import type { ControlProfile } from "@/types/control";
import type { Device } from "@/types/device";
import type { ProviderCapability } from "@/types/integration";

const mocks = vi.hoisted(() => ({
  refresh: vi.fn(),
  runDeviceControlAction: vi.fn(),
  updateDeviceIdentity: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: mocks.refresh }),
}));
vi.mock("@/lib/api", () => ({
  runDeviceControlAction: mocks.runDeviceControlAction,
  updateDeviceIdentity: mocks.updateDeviceIdentity,
}));

const device: Device = {
  id: 7,
  name: null,
  ip_address: "192.168.1.72",
  network_cidr: "192.168.1.0/24",
  mac_address: "AA:BB:CC:DD:EE:FF",
  hostname: null,
  vendor: "Xiaomi",
  status: "online",
  latency_ms: 12,
  first_seen: "2026-09-08T12:00:00Z",
  last_seen: "2026-09-08T12:01:00Z",
  created_at: "2026-09-08T12:00:00Z",
  updated_at: "2026-09-08T12:01:00Z",
  is_gateway: false,
  device_type: null,
  owner: null,
  profile_id: null,
  trust_state: "unknown",
  internet_access: "allowed",
  lan_access: "allowed",
  paused_until: null,
  quarantine_reason: null,
  quarantined_at: null,
  service_ports: [],
};

const childProfile: ControlProfile = {
  id: 2,
  name: "Child",
  description: null,
  internet_enabled: true,
  safe_search_enabled: true,
  blocked_categories: [],
  created_at: "2026-09-08T12:00:00Z",
  updated_at: "2026-09-08T12:00:00Z",
  device_ids: [],
  device_count: 0,
  blocked_requests_today: 0,
  schedules: [],
  domain_rules: [],
  schedule_state: "allowed",
  next_schedule_change: null,
};

const provider: ProviderCapability = {
  provider_id: "monitoring_only",
  display_name: "Generic / Monitoring Only",
  kind: "network",
  configured: false,
  status: "connected",
  message: "Router control is not configured.",
  version: null,
  capabilities: {
    block_internet: false,
    unblock_internet: false,
    quarantine_device: false,
    release_device: false,
    firewall_rules: false,
  },
};

describe("DeviceAccessPanel", () => {
  it("keeps unsupported router actions disabled and saves a manual name", async () => {
    mocks.updateDeviceIdentity.mockResolvedValue({
      ...device,
      name: "João's Tablet",
      profile_id: 2,
    });
    render(
      <DeviceAccessPanel
        initial={device}
        profiles={[childProfile]}
        provider={provider}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Pause Internet 1 hour" }),
    ).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "João's Tablet" },
    });
    fireEvent.change(screen.getByLabelText("Parental profile"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save identity" }));

    await waitFor(() =>
      expect(mocks.updateDeviceIdentity).toHaveBeenCalledWith(
        7,
        expect.objectContaining({
          name: "João's Tablet",
          profile_id: 2,
        }),
      ),
    );
    expect(
      await screen.findByText(/identity and profile saved/i),
    ).toBeInTheDocument();
  });
});
