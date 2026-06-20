// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

// The UI-side mirror of argus/fleet/promql.py: the readable label, unit, and
// thresholds for each metric key. Kept in sync by hand (a small, stable set).

export type Quality = "good" | "warn" | "bad" | "neutral";

export type Unit = "seconds" | "ratio" | "count" | "per_second";

export interface MetricMeta {
  key: string;
  label: string;
  unit: Unit;
  warn?: number;
  bad?: number;
  higherIsWorse?: boolean;
}

export const METRIC_META: MetricMeta[] = [
  { key: "shards_up", label: "Shards up", unit: "count" },
  { key: "guilds", label: "Guilds", unit: "count" },
  { key: "cached_users", label: "Cached users", unit: "count" },
  { key: "latency_seconds", label: "Gateway latency", unit: "seconds", warn: 0.3, bad: 1.0, higherIsWorse: true },
  { key: "error_rate", label: "Error rate", unit: "ratio", warn: 0.01, bad: 0.05, higherIsWorse: true },
  { key: "duration_p95_seconds", label: "Command p95", unit: "seconds", warn: 1.0, bad: 3.0, higherIsWorse: true },
  { key: "interactions_rate", label: "Interactions/sec", unit: "per_second" },
  { key: "ratelimits_rate", label: "Rate limits/sec", unit: "per_second", warn: 0.1, bad: 1.0, higherIsWorse: true },
  { key: "uptime_seconds", label: "Uptime", unit: "seconds" },
];

export const META_BY_KEY: Record<string, MetricMeta> = Object.fromEntries(
  METRIC_META.map((m) => [m.key, m]),
);

function formatDuration(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

export function formatMetric(key: string, value: number): string {
  const meta = META_BY_KEY[key];
  const unit = meta?.unit ?? "count";
  if (!Number.isFinite(value)) return "-";
  switch (unit) {
    case "ratio":
      return `${(value * 100).toFixed(2)}%`;
    case "per_second":
      return `${value.toFixed(2)}/s`;
    case "seconds":
      return formatDuration(value);
    default:
      return Math.round(value).toLocaleString();
  }
}

// Judge a value against its thresholds. Only metrics with a "worse" direction
// are graded; everything else is neutral (informational counts).
export function qualityOf(key: string, value: number): Quality {
  const meta = META_BY_KEY[key];
  if (!meta || !meta.higherIsWorse || meta.warn === undefined || meta.bad === undefined) {
    return "neutral";
  }
  if (value >= meta.bad) return "bad";
  if (value >= meta.warn) return "warn";
  return "good";
}
