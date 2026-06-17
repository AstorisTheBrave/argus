import { describe, expect, it } from "vitest";

import { bucketsFromSamples, histogramQuantile } from "./quantile";

describe("histogramQuantile", () => {
  const buckets = [
    { le: 0.1, count: 0 },
    { le: 0.5, count: 5 },
    { le: 1.0, count: 8 },
    { le: Infinity, count: 10 },
  ];

  it("interpolates within the chosen bucket", () => {
    // median (rank 5) lands at the top of the 0.5 bucket
    expect(histogramQuantile(0.5, buckets)).toBeCloseTo(0.5, 5);
  });

  it("returns NaN for empty or zero-count buckets", () => {
    expect(Number.isNaN(histogramQuantile(0.9, []))).toBe(true);
    expect(Number.isNaN(histogramQuantile(0.9, [{ le: Infinity, count: 0 }]))).toBe(true);
  });

  it("does not interpolate into the +Inf bucket", () => {
    expect(histogramQuantile(0.99, buckets)).toBe(1.0);
  });
});

describe("bucketsFromSamples", () => {
  it("sums bucket samples across label sets and sorts by le", () => {
    const samples: { name: string; labels: Record<string, string>; value: number }[] = [
      { name: "d_bucket", labels: { command: "a", le: "0.5" }, value: 2 },
      { name: "d_bucket", labels: { command: "b", le: "0.5" }, value: 3 },
      { name: "d_bucket", labels: { command: "a", le: "+Inf" }, value: 4 },
      { name: "d_sum", labels: { command: "a" }, value: 9 },
    ];
    const buckets = bucketsFromSamples(samples, "d");
    expect(buckets).toEqual([
      { le: 0.5, count: 5 },
      { le: Infinity, count: 4 },
    ]);
  });
});
