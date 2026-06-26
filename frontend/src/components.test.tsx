// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SECTIONS, Sidebar, StatCard } from "./components";

describe("StatCard", () => {
  it("renders the label, value and unit", () => {
    render(<StatCard label="Guilds" value="42" unit="x" />);
    expect(screen.getByText("Guilds")).toBeTruthy();
    expect(screen.getByText("42")).toBeTruthy();
    expect(screen.getByText("x")).toBeTruthy();
  });
});

describe("Sidebar", () => {
  it("includes a Setup entry so the wizard is reachable from the nav", () => {
    expect(SECTIONS.map((s) => s.id)).toContain("setup");
    expect(SECTIONS.find((s) => s.id === "setup")?.label).toBe("Setup");
  });

  it("renders every section as a nav item", () => {
    render(
      <Sidebar
        active="overview"
        onSelect={() => {}}
        clusters={[]}
        cluster="*"
        onCluster={() => {}}
        version="1.2.3"
      />,
    );
    for (const section of SECTIONS) {
      expect(screen.getByText(section.label)).toBeTruthy();
    }
  });
});
