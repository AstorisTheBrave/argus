// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

// Small selectors over a Snapshot. Counter families are keyed by their base
// name (prometheus strips _total from the family), so counter totals are the
// samples whose name ends in _total.

import type { Sample, Snapshot } from "./prom";

export function samples(snap: Snapshot, family: string): Sample[] {
  return snap.metrics[family]?.samples ?? [];
}

function matches(sample: Sample, labels: Record<string, string>): boolean {
  return Object.entries(labels).every(([k, v]) => sample.labels[k] === v);
}

export function gaugeValue(snap: Snapshot, family: string, labels: Record<string, string> = {}): number {
  const found = samples(snap, family).find((s) => matches(s, labels));
  return found ? found.value : NaN;
}

export function counterTotal(snap: Snapshot, family: string, labels: Record<string, string> = {}): number {
  return samples(snap, family)
    .filter((s) => s.name.endsWith("_total") && matches(s, labels))
    .reduce((acc, s) => acc + s.value, 0);
}

export function sumByLabel(snap: Snapshot, family: string, label: string): Map<string, number> {
  const out = new Map<string, number>();
  for (const s of samples(snap, family)) {
    if (!s.name.endsWith("_total")) continue;
    const key = s.labels[label] ?? "";
    out.set(key, (out.get(key) ?? 0) + s.value);
  }
  return out;
}

export function clusters(snap: Snapshot): string[] {
  const set = new Set<string>();
  for (const s of samples(snap, "discord_guilds")) {
    if (s.labels.cluster) set.add(s.labels.cluster);
  }
  return [...set].sort();
}

export function infoValue(snap: Snapshot, family: string, key: string): string {
  const found = samples(snap, family).find((s) => s.labels[key] !== undefined);
  return found ? found.labels[key] : "";
}
