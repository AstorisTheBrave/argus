// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatCard } from "./components";

describe("StatCard", () => {
  it("renders the label, value and unit", () => {
    render(<StatCard label="Guilds" value="42" unit="x" />);
    expect(screen.getByText("Guilds")).toBeTruthy();
    expect(screen.getByText("42")).toBeTruthy();
    expect(screen.getByText("x")).toBeTruthy();
  });
});
