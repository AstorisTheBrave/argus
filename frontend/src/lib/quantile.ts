// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

// Prometheus-style histogram_quantile over cumulative buckets, with linear
// interpolation within the chosen bucket.

export interface Bucket {
  le: number; // upper bound; Infinity for the +Inf bucket
  count: number; // cumulative count up to le
}

export function histogramQuantile(q: number, buckets: Bucket[]): number {
  if (buckets.length === 0) return NaN;
  const sorted = [...buckets].sort((a, b) => a.le - b.le);
  const total = sorted[sorted.length - 1].count;
  if (total === 0) return NaN;

  const rank = q * total;
  let prevCount = 0;
  let prevLe = 0;
  for (const bucket of sorted) {
    if (bucket.count >= rank) {
      if (bucket.le === Infinity) return prevLe; // cannot interpolate into +Inf
      const bucketCount = bucket.count - prevCount;
      if (bucketCount === 0) return bucket.le;
      return prevLe + (bucket.le - prevLe) * ((rank - prevCount) / bucketCount);
    }
    prevCount = bucket.count;
    if (bucket.le !== Infinity) prevLe = bucket.le;
  }
  return prevLe;
}

// Extract sorted cumulative buckets for one histogram family from a Snapshot's
// samples, summed across label sets (e.g. across commands).
export function bucketsFromSamples(
  samples: { name: string; labels: Record<string, string>; value: number }[],
  base: string,
): Bucket[] {
  const byLe = new Map<number, number>();
  for (const s of samples) {
    if (s.name !== `${base}_bucket`) continue;
    const leRaw = s.labels.le;
    const le = leRaw === "+Inf" ? Infinity : Number(leRaw);
    byLe.set(le, (byLe.get(le) ?? 0) + s.value);
  }
  return [...byLe.entries()].map(([le, count]) => ({ le, count })).sort((a, b) => a.le - b.le);
}
