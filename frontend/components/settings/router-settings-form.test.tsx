import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RouterSettingsForm } from "@/components/settings/router-settings-form";

const mocks = vi.hoisted(() => ({
  configureRouter: vi.fn(),
  deleteRouterIntegration: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  configureRouter: mocks.configureRouter,
  deleteRouterIntegration: mocks.deleteRouterIntegration,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: mocks.refresh }),
}));

describe("RouterSettingsForm", () => {
  beforeEach(() => vi.clearAllMocks());

  it("requires confirmation before enabling and does not prefill secrets", async () => {
    mocks.configureRouter.mockResolvedValue({
      provider_id: "openwrt",
      display_name: "OpenWrt",
      kind: "network",
      enabled: true,
      server_url: "http://192.168.1.1",
      credential_set: true,
      status: "connected",
      message: "OpenWrt is connected.",
      version: null,
    });
    render(<RouterSettingsForm initial={null} />);

    fireEvent.change(screen.getByLabelText("Router provider"), {
      target: { value: "openwrt" },
    });
    expect(screen.getByLabelText("Password (leave blank to keep)")).toHaveValue(
      "",
    );
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "root" },
    });
    fireEvent.change(screen.getByLabelText("Password (leave blank to keep)"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getAllByRole("checkbox")[0]);
    expect(mocks.configureRouter).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Save router integration" }),
    ).toBeDisabled();

    fireEvent.click(screen.getAllByRole("checkbox")[1]);
    fireEvent.click(
      screen.getByRole("button", { name: "Save router integration" }),
    );

    await waitFor(() =>
      expect(mocks.configureRouter).toHaveBeenCalledWith({
        provider_id: "openwrt",
        server_url: "http://192.168.1.1",
        username: "root",
        password: "secret",
        enabled: true,
        confirm_state_changes: true,
      }),
    );
  });
});
