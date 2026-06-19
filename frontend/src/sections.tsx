// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { useMemo } from "react";
import type uPlot from "uplot";

import { LineChart, StatCard } from "./components";
import type { Snapshot } from "./lib/prom";
import { bucketsFromSamples, histogramQuantile } from "./lib/quantile";
import { counterTotal, gaugeValue, histogramAvg, samples } from "./lib/select";
import type { Frame } from "./useDashboard";

const ACCENT = "#6aa8ff";
const ACCENT2 = "#b48cff";

function fmt(n: number): string {
  if (Number.isNaN(n)) return "-";
  return Number.isInteger(n) ? n.toString() : n.toFixed(2);
}

function fmtUptime(seconds: number): string {
  if (Number.isNaN(seconds) || seconds <= 0) return "-";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function clusterLabels(cluster: string): Record<string, string> {
  return cluster === "*" ? {} : { cluster };
}

function levelData(frames: Frame[], pick: (s: Snapshot) => number): uPlot.AlignedData {
  const t0 = frames.length > 0 ? frames[0].t : 0;
  const xs = frames.map((f) => (f.t - t0) / 1000);
  const ys = frames.map((f) => pick(f.snap));
  return [xs, ys];
}

function rateData(frames: Frame[], pick: (s: Snapshot) => number): uPlot.AlignedData {
  const t0 = frames.length > 0 ? frames[0].t : 0;
  const xs: number[] = [];
  const ys: (number | null)[] = [];
  for (let i = 0; i < frames.length; i++) {
    xs.push((frames[i].t - t0) / 1000);
    if (i === 0) {
      ys.push(null);
      continue;
    }
    const dt = (frames[i].t - frames[i - 1].t) / 1000;
    const dv = pick(frames[i].snap) - pick(frames[i - 1].snap);
    ys.push(dt > 0 ? Math.max(0, dv / dt) : null);
  }
  return [xs, ys];
}

function maxLatency(snap: Snapshot): number {
  const values = samples(snap, "discord_shard_latency_seconds").map((s) => s.value);
  return values.length > 0 ? Math.max(...values) : 0;
}

export function Overview({ latest, frames, cluster }: { latest: Snapshot; frames: Frame[]; cluster: string }) {
  const cl = clusterLabels(cluster);
  const data = useMemo(() => levelData(frames, maxLatency), [frames]);
  return (
    <div className="section">
      <div className="grid">
        <StatCard label="Status" value={gaugeValue(latest, "argus_up") === 1 ? "up" : "down"} />
        <StatCard
          label="Shards"
          value={`${fmt(gaugeValue(latest, "discord_shards_connected", cl))} / ${fmt(gaugeValue(latest, "discord_shards_configured", cl))}`}
        />
        <StatCard label="Guilds" value={fmt(gaugeValue(latest, "discord_guilds", cl))} />
        <StatCard label="Cached users" value={fmt(gaugeValue(latest, "discord_cached_users", cl))} />
        <StatCard label="Voice clients" value={fmt(gaugeValue(latest, "discord_voice_clients", cl))} />
        <StatCard label="Emojis" value={fmt(gaugeValue(latest, "discord_emojis", cl))} />
        <StatCard
          label="Commands"
          value={fmt(gaugeValue(latest, "discord_app_commands_registered", cl))}
        />
        <StatCard label="Uptime" value={fmtUptime(gaugeValue(latest, "discord_uptime_seconds", cl))} />
      </div>
      <LineChart title="Max shard latency (s)" data={data} series={[{ label: "latency", stroke: ACCENT }]} />
    </div>
  );
}

export function Interactions({ latest, frames }: { latest: Snapshot; frames: Frame[] }) {
  const totalCommands = counterTotal(latest, "discord_app_commands");
  const errors = counterTotal(latest, "discord_app_commands", { status: "error" });
  const errPct = totalCommands > 0 ? (errors / totalCommands) * 100 : 0;
  const buckets = bucketsFromSamples(
    samples(latest, "discord_app_command_duration_seconds"),
    "discord_app_command_duration_seconds",
  );
  const data = useMemo(
    () => rateData(frames, (s) => counterTotal(s, "discord_interactions")),
    [frames],
  );
  return (
    <div className="section">
      <div className="grid">
        <StatCard label="Interactions" value={fmt(counterTotal(latest, "discord_interactions"))} />
        <StatCard label="App commands" value={fmt(totalCommands)} />
        <StatCard label="Error rate" value={fmt(errPct)} unit="%" />
        <StatCard
          label="Duration avg"
          value={fmt(histogramAvg(latest, "discord_app_command_duration_seconds"))}
          unit="s"
        />
        <StatCard label="Duration p95" value={fmt(histogramQuantile(0.95, buckets))} unit="s" />
      </div>
      <LineChart
        title="Interaction rate (per s)"
        data={data}
        series={[{ label: "interactions/s", stroke: ACCENT }]}
      />
    </div>
  );
}

export function Gateway({ latest, frames }: { latest: Snapshot; frames: Frame[] }) {
  const data = useMemo(
    () => rateData(frames, (s) => counterTotal(s, "discord_gateway_events")),
    [frames],
  );
  return (
    <div className="section">
      <div className="grid">
        <StatCard label="Gateway events" value={fmt(counterTotal(latest, "discord_gateway_events"))} />
        <StatCard label="Rate limits" value={fmt(counterTotal(latest, "discord_ratelimits"))} />
        <StatCard label="Disconnects" value={fmt(counterTotal(latest, "discord_shard_disconnects"))} />
        <StatCard label="Reconnects" value={fmt(counterTotal(latest, "discord_shard_reconnects"))} />
      </div>
      <LineChart
        title="Gateway events (per s)"
        data={data}
        series={[{ label: "events/s", stroke: ACCENT2 }]}
      />
    </div>
  );
}
