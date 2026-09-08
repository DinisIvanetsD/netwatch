import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdGuardSettingsForm } from "@/components/settings/adguard-settings-form";
import type { AdGuardIntegration } from "@/types/integration";

const mocks = vi.hoisted(() => ({
  configureAdGuard: vi.fn(),
  testAdGuard: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  configureAdGuard: mocks.configureAdGuard,
  testAdGuard: mocks.testAdGuard,
}));

const initial: AdGuardIntegration = {
  provider_id: "adguard_home",
  display_name: "AdGuard Home",
  kind: "dns",
  enabled: true,
  server_url: "http://adguardhome",
  username: "netwatch-admin",
  password_set: true,
  status: "connected",
  message: "AdGuard Home is connected.",
  version: "v0.107.79",
};

describe("AdGuardSettingsForm", () => {
  beforeEach(() => vi.clearAllMocks());

  it("tests an existing connection without asking for the stored password", async () => {
    mocks.testAdGuard.mockResolvedValue({
      status: "connected",
      message: "Connection verified.",
      version: "v0.107.79",
    });
    render(<AdGuardSettingsForm initial={initial} />);

    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));

    await waitFor(() =>
      expect(mocks.testAdGuard).toHaveBeenCalledWith({
        server_url: "http://adguardhome",
        username: "netwatch-admin",
      }),
    );
    expect(await screen.findByText("Connection verified.")).toBeInTheDocument();
  });
});
