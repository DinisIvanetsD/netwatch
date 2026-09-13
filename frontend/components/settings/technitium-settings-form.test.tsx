import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TechnitiumSettingsForm } from "@/components/settings/technitium-settings-form";
import type { TechnitiumIntegration } from "@/types/integration";

const mocks = vi.hoisted(() => ({
  configureTechnitium: vi.fn(),
  testTechnitium: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  configureTechnitium: mocks.configureTechnitium,
  testTechnitium: mocks.testTechnitium,
}));

const initial: TechnitiumIntegration = {
  provider_id: "technitium_dns",
  display_name: "Technitium DNS Server",
  kind: "dns",
  enabled: true,
  server_url: "http://technitium:5380",
  username: "admin",
  dns_port: 5453,
  password_set: true,
  status: "connected",
  message: "Technitium DNS Server is connected.",
  version: "15.4.0",
};

describe("TechnitiumSettingsForm", () => {
  beforeEach(() => vi.clearAllMocks());

  it("tests an existing connection without requesting the stored password", async () => {
    mocks.testTechnitium.mockResolvedValue({
      status: "connected",
      message: "Connection verified.",
      version: "15.4.0",
    });
    render(<TechnitiumSettingsForm initial={initial} />);

    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));

    await waitFor(() =>
      expect(mocks.testTechnitium).toHaveBeenCalledWith({
        server_url: "http://technitium:5380",
        username: "admin",
      }),
    );
    expect(await screen.findByText("Connection verified.")).toBeInTheDocument();
  });

  it("shows URL guidance without exposing the stored password", () => {
    render(<TechnitiumSettingsForm initial={initial} />);

    expect(screen.getByText("http://127.0.0.1:5380")).toBeInTheDocument();
    expect(screen.getByText("http://technitium:5380")).toBeInTheDocument();
    expect(screen.getByLabelText("Password (leave blank to keep)")).toHaveValue(
      "",
    );
    expect(screen.getByText(/not DNS port 53/)).toBeInTheDocument();
  });

  it.each([
    [
      "rate_limited",
      /rate-limited.*Wait before trying again; do not retry repeatedly/i,
    ],
    [
      "authentication_failed",
      /password was not accepted.*Verify it in Technitium/i,
    ],
  ])("explains the %s status", async (status, expectedMessage) => {
    mocks.testTechnitium.mockResolvedValue({
      status,
      message: "Backend detail",
      version: null,
    });
    render(<TechnitiumSettingsForm initial={initial} />);

    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));

    expect(await screen.findByText(expectedMessage)).toBeInTheDocument();
    expect(screen.queryByText("Backend detail")).not.toBeInTheDocument();
  });
});
