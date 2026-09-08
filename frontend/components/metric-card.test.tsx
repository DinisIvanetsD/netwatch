import { render, screen } from "@testing-library/react";
import { Activity } from "lucide-react";
import { describe, expect, it } from "vitest";

import { MetricCard } from "@/components/metric-card";

describe("MetricCard", () => {
  it("renders a labelled network metric", () => {
    render(
      <MetricCard
        label="ONLINE"
        value="19"
        detail="79% availability"
        icon={Activity}
      />,
    );
    expect(screen.getByText("ONLINE")).toBeInTheDocument();
    expect(screen.getByText("19")).toBeInTheDocument();
    expect(screen.getByText("79% availability")).toBeInTheDocument();
  });
});
