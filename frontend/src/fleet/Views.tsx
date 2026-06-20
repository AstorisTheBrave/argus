// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { METRIC_META, formatMetric, qualityOf } from "./format";
import type { ClusterView, FleetGroupView, FleetView } from "./types";

function RollupCards({ metrics }: { metrics: Record<string, number> }) {
  return (
    <div className="grid">
      {METRIC_META.map((m) => {
        const value = metrics[m.key] ?? 0;
        return (
          <div key={m.key} className={`nimble-glass--flat stat fleet-stat ${qualityOf(m.key, value)}`}>
            <div className="label">{m.label}</div>
            <div className="value nimble-mono">{formatMetric(m.key, value)}</div>
          </div>
        );
      })}
    </div>
  );
}

function HealthPill({ up, total }: { up: number; total: number }) {
  const quality = up === total ? "good" : up === 0 ? "bad" : "warn";
  return (
    <span className={`fleet-pill ${quality}`}>
      {up}/{total} up
    </span>
  );
}

export function Global({
  view,
  onFleet,
}: {
  view: FleetView;
  onFleet: (name: string) => void;
}) {
  return (
    <div className="section">
      <h2>Fleet overview</h2>
      <RollupCards metrics={view.global} />
      <h3>Fleets</h3>
      <div className="fleet-grid">
        {view.fleets.map((f) => (
          <button key={f.name} className="nimble-glass--flat fleet-card" onClick={() => onFleet(f.name)}>
            <div className="fleet-card-head">
              <span className="fleet-name">{f.name}</span>
              <HealthPill up={f.clusters_up} total={f.clusters_total} />
            </div>
            <div className="fleet-card-body nimble-mono">
              {formatMetric("guilds", f.rollup.guilds ?? 0)} guilds
            </div>
          </button>
        ))}
        {view.fleets.length === 0 && <p className="muted">No clusters have registered yet.</p>}
      </div>
    </div>
  );
}

export function Fleet({
  group,
  onCluster,
}: {
  group: FleetGroupView;
  onCluster: (number: number) => void;
}) {
  return (
    <div className="section">
      <h2>
        {group.name} <HealthPill up={group.clusters_up} total={group.clusters_total} />
      </h2>
      <RollupCards metrics={group.rollup} />
      <h3>Clusters</h3>
      <div className="fleet-grid">
        {group.clusters.map((c) => (
          <button
            key={c.number}
            className={`nimble-glass--flat fleet-card ${c.status}`}
            onClick={() => onCluster(c.number)}
          >
            <div className="fleet-card-head">
              <span className="fleet-name">
                {group.name} #{c.number}
              </span>
              <span className={`fleet-pill ${c.status === "up" ? "good" : "bad"}`}>{c.status}</span>
            </div>
            <div className="fleet-card-body nimble-mono">
              {formatMetric("guilds", c.metrics.guilds ?? 0)} guilds
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export function Cluster({ cluster, fleet }: { cluster: ClusterView; fleet: string }) {
  return (
    <div className="section">
      <h2>
        {fleet} #{cluster.number}{" "}
        <span className={`fleet-pill ${cluster.status === "up" ? "good" : "bad"}`}>
          {cluster.status}
        </span>
      </h2>
      <p className="muted nimble-mono">
        {cluster.identity} - last seen {cluster.last_seen}
      </p>
      <RollupCards metrics={cluster.metrics} />
    </div>
  );
}
