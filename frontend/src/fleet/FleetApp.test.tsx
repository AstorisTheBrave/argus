// @vitest-environment jsdom
// SPDX-License-Identifier: AGPL-3.0-or-later
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FleetApp } from "./FleetApp";

const VIEW = {
  generated_at: "2026-06-21T00:00:00+00:00",
  global: { guilds: 30, shards_up: 4, error_rate: 0 },
  fleets: [{ name: "asia", clusters_up: 2, clusters_total: 2, rollup: { guilds: 30 }, clusters: [] }],
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => VIEW }) as unknown as Response),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("FleetApp", () => {
  it("polls the fleet view and renders the Global tier", async () => {
    render(<FleetApp token={null} version="9.9.9" />);
    await waitFor(() => expect(screen.getByText("Fleet overview")).toBeTruthy());
    expect(screen.getByText("asia")).toBeTruthy();
    expect(screen.getByText("2/2 up")).toBeTruthy();
    expect(screen.getByText(/Argus Fleet v9.9.9/)).toBeTruthy();
  });
});
