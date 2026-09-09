import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DomainRulesEditor } from "@/components/control/domain-rules-editor";

const mocks = vi.hoisted(() => ({
  createDomainRule: vi.fn(),
  deleteDomainRule: vi.fn(),
  retryDomainRule: vi.fn(),
}));

vi.mock("@/lib/api", () => mocks);

describe("DomainRulesEditor", () => {
  it("creates a network-wide rule and shows confirmed enforcement", async () => {
    mocks.createDomainRule.mockResolvedValue({
      id: 9,
      scope_type: "global",
      scope_id: null,
      domain: "example.com",
      action: "block",
      include_subdomains: true,
      reason: "Administrator network-wide rule",
      enabled: true,
      expires_at: null,
      enforcement_status: "active",
      enforcement_error: null,
      last_applied_at: "2026-09-09T12:00:00Z",
      created_at: "2026-09-09T12:00:00Z",
    });

    render(
      <DomainRulesEditor
        scopeType="global"
        scopeId={null}
        title="Network-wide website rules"
        description="DNS rules"
        reason="Administrator network-wide rule"
        emptyMessage="No rules"
        initialRules={[]}
      />,
    );
    fireEvent.change(screen.getByLabelText("Domain"), {
      target: { value: "example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add rule" }));

    await waitFor(() =>
      expect(mocks.createDomainRule).toHaveBeenCalledWith({
        scope_type: "global",
        scope_id: null,
        domain: "example.com",
        action: "block",
        include_subdomains: true,
        reason: "Administrator network-wide rule",
      }),
    );
    expect(
      await screen.findByText("Rule applied by the DNS provider."),
    ).toBeInTheDocument();
    expect(screen.getByText("example.com")).toBeInTheDocument();
  });
});
