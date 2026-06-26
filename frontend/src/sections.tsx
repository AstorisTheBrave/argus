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
const GREEN = "#4ade80";
const RED = "#fb7185";

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

function rateSeries(frames: Frame[], pick: (s: Snapshot) => number): (number | null)[] {
  const ys: (number | null)[] = [];
  for (let i = 0; i < frames.length; i++) {
    if (i === 0) {
      ys.push(null);
      continue;
    }
    const dt = (frames[i].t - frames[i - 1].t) / 1000;
    const dv = pick(frames[i].snap) - pick(frames[i - 1].snap);
    ys.push(dt > 0 ? Math.max(0, dv / dt) : null);
  }
  return ys;
}

function rateData(frames: Frame[], pick: (s: Snapshot) => number): uPlot.AlignedData {
  const t0 = frames.length > 0 ? frames[0].t : 0;
  const xs = frames.map((f) => (f.t - t0) / 1000);
  return [xs, rateSeries(frames, pick)];
}

// Several rate series aligned on one time axis (Grafana multi-line panels).
function multiRateData(
  frames: Frame[],
  picks: ((s: Snapshot) => number)[],
): uPlot.AlignedData {
  const t0 = frames.length > 0 ? frames[0].t : 0;
  const xs = frames.map((f) => (f.t - t0) / 1000);
  return [xs, ...picks.map((p) => rateSeries(frames, p))] as uPlot.AlignedData;
}

function levelMulti(frames: Frame[], picks: ((s: Snapshot) => number)[]): uPlot.AlignedData {
  const t0 = frames.length > 0 ? frames[0].t : 0;
  const xs = frames.map((f) => (f.t - t0) / 1000);
  return [xs, ...picks.map((p) => frames.map((f) => p(f.snap)))] as uPlot.AlignedData;
}

const RATE1 = (s: number) => s.toFixed(1);

function maxLatency(snap: Snapshot): number {
  const values = samples(snap, "discord_shard_latency_seconds").map((s) => s.value);
  return values.length > 0 ? Math.max(...values) : 0;
}

export function Overview({ latest, frames, cluster }: { latest: Snapshot; frames: Frame[]; cluster: string }) {
  const cl = clusterLabels(cluster);
  const latency = useMemo(() => levelData(frames, maxLatency), [frames]);
  const population = useMemo(() => {
    const labels = clusterLabels(cluster);
    return levelMulti(frames, [
      (s) => gaugeValue(s, "discord_guilds", labels),
      (s) => gaugeValue(s, "discord_voice_clients", labels),
    ]);
  }, [frames, cluster]);
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
      <div className="panel-grid">
        <LineChart
          title="Max shard latency"
          unit="s"
          data={latency}
          series={[{ label: "latency", stroke: ACCENT }]}
        />
        <LineChart
          title="Population"
          format={(n) => String(Math.round(n))}
          data={population}
          series={[
            { label: "guilds", stroke: ACCENT2 },
            { label: "voice", stroke: GREEN },
          ]}
        />
      </div>
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
  const rate = useMemo(
    () => rateData(frames, (s) => counterTotal(s, "discord_interactions")),
    [frames],
  );
  const outcomes = useMemo(
    () =>
      multiRateData(frames, [
        (s) => counterTotal(s, "discord_app_commands", { status: "success" }),
        (s) => counterTotal(s, "discord_app_commands", { status: "error" }),
      ]),
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
      <div className="panel-grid">
        <LineChart
          title="Interaction rate"
          unit="/s"
          format={RATE1}
          data={rate}
          series={[{ label: "interactions/s", stroke: ACCENT }]}
        />
        <LineChart
          title="App commands by outcome"
          unit="/s"
          format={RATE1}
          data={outcomes}
          series={[
            { label: "success/s", stroke: GREEN },
            { label: "error/s", stroke: RED },
          ]}
        />
      </div>
    </div>
  );
}

export function Gateway({ latest, frames }: { latest: Snapshot; frames: Frame[] }) {
  const events = useMemo(
    () => rateData(frames, (s) => counterTotal(s, "discord_gateway_events")),
    [frames],
  );
  const shardHealth = useMemo(
    () =>
      multiRateData(frames, [
        (s) => counterTotal(s, "discord_shard_disconnects"),
        (s) => counterTotal(s, "discord_shard_reconnects"),
        (s) => counterTotal(s, "discord_ratelimits"),
      ]),
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
      <div className="panel-grid">
        <LineChart
          title="Gateway events"
          unit="/s"
          format={RATE1}
          data={events}
          series={[{ label: "events/s", stroke: ACCENT2 }]}
        />
        <LineChart
          title="Shard health & rate limits"
          unit="/s"
          format={RATE1}
          data={shardHealth}
          series={[
            { label: "disconnects/s", stroke: RED },
            { label: "reconnects/s", stroke: GREEN },
            { label: "ratelimits/s", stroke: ACCENT },
          ]}
        />
      </div>
    </div>
  );
}
