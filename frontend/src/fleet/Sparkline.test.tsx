// @vitest-environment jsdom
// SPDX-License-Identifier: AGPL-3.0-or-later
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Sparkline } from "./Sparkline";

afterEach(cleanup);

describe("Sparkline", () => {
  it("draws a polyline with one point per value", () => {
    const { container } = render(<Sparkline values={[1, 2, 3]} width={100} height={20} />);
    const poly = container.querySelector("polyline");
    expect(poly).not.toBeNull();
    expect(poly!.getAttribute("points")!.trim().split(" ")).toHaveLength(3);
  });

  it("renders an empty svg for fewer than two points", () => {
    const { container } = render(<Sparkline values={[5]} />);
    expect(container.querySelector("polyline")).toBeNull();
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("handles a flat series without dividing by zero", () => {
    const { container } = render(<Sparkline values={[4, 4, 4]} />);
    const points = container.querySelector("polyline")!.getAttribute("points")!;
    expect(points.includes("NaN")).toBe(false);
  });
});
