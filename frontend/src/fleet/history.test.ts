// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";

import { seriesFor, type TrendPoint } from "./history";

describe("seriesFor", () => {
  const history: TrendPoint[] = [
    { t: "t1", metrics: { guilds: 1, latency_seconds: 0.1 } },
    { t: "t2", metrics: { guilds: 3 } },
  ];

  it("extracts a key's values across points", () => {
    expect(seriesFor(history, "guilds")).toEqual([1, 3]);
  });

  it("defaults missing values to 0", () => {
    expect(seriesFor(history, "latency_seconds")).toEqual([0.1, 0]);
  });

  it("returns [] for empty history", () => {
    expect(seriesFor([], "guilds")).toEqual([]);
  });
});
