// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";

import { formatMetric, qualityOf } from "./format";

describe("formatMetric", () => {
  it("formats ratios as percentages", () => {
    expect(formatMetric("error_rate", 0.0123)).toBe("1.23%");
  });

  it("formats sub-second durations as milliseconds", () => {
    expect(formatMetric("latency_seconds", 0.082)).toBe("82ms");
  });

  it("formats longer durations as seconds and minutes", () => {
    expect(formatMetric("duration_p95_seconds", 2.5)).toBe("2.50s");
    expect(formatMetric("uptime_seconds", 90)).toBe("1m 30s");
  });

  it("formats per-second rates", () => {
    expect(formatMetric("interactions_rate", 3.2)).toBe("3.20/s");
  });

  it("rounds counts", () => {
    expect(formatMetric("guilds", 1234.6)).toBe("1,235");
  });

  it("guards non-finite values", () => {
    expect(formatMetric("guilds", NaN)).toBe("-");
  });
});

describe("qualityOf", () => {
  it("grades higher-is-worse metrics by threshold", () => {
    expect(qualityOf("error_rate", 0.0)).toBe("good");
    expect(qualityOf("error_rate", 0.02)).toBe("warn");
    expect(qualityOf("error_rate", 0.1)).toBe("bad");
  });

  it("treats plain counts as neutral", () => {
    expect(qualityOf("guilds", 999)).toBe("neutral");
  });
});
