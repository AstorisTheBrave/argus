// @vitest-environment jsdom
// SPDX-License-Identifier: AGPL-3.0-or-later
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Global } from "./Views";
import type { FleetView } from "./types";

afterEach(cleanup);

const VIEW: FleetView = {
  generated_at: "2026-06-20T00:00:00+00:00",
  global: { guilds: 30, shards_up: 4, error_rate: 0.0 },
  fleets: [
    {
      name: "asia",
      clusters_up: 2,
      clusters_total: 3,
      rollup: { guilds: 20 },
      clusters: [],
    },
    {
      name: "europe",
      clusters_up: 1,
      clusters_total: 1,
      rollup: { guilds: 10 },
      clusters: [],
    },
  ],
};

describe("Global", () => {
  it("renders rollup cards and a fleet grid with health", () => {
    render(<Global view={VIEW} onFleet={() => {}} />);
    expect(screen.getByText("Fleet overview")).toBeTruthy();
    expect(screen.getByText("asia")).toBeTruthy();
    expect(screen.getByText("2/3 up")).toBeTruthy();
    expect(screen.getByText("1/1 up")).toBeTruthy();
  });

  it("invokes onFleet when a fleet card is clicked", () => {
    const onFleet = vi.fn();
    render(<Global view={VIEW} onFleet={onFleet} />);
    fireEvent.click(screen.getByText("asia"));
    expect(onFleet).toHaveBeenCalledWith("asia");
  });

  it("shows an empty state when no clusters have registered", () => {
    render(
      <Global
        view={{ generated_at: "t", global: {}, fleets: [] }}
        onFleet={() => {}}
      />,
    );
    expect(screen.getByText(/No clusters have registered/)).toBeTruthy();
  });
});
