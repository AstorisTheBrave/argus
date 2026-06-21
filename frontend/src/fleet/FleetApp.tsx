// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { useState } from "react";

import { Analytics } from "./Analytics";
import { useFleet } from "./useFleet";
import { Cluster, Fleet, Global } from "./Views";

// The fleet control plane is a three-tier drill-down: Global -> Fleet -> Cluster
// -> Shard, plus an optional Analytics view (per-guild, ClickHouse). Selection is
// local state; the live view is re-polled each tick so a cluster going down
// updates in place without losing the current screen.
export function FleetApp({
  token,
  version,
  analyticsEnabled = false,
}: {
  token: string | null;
  version: string;
  analyticsEnabled?: boolean;
}) {
  const { view, error } = useFleet(token);
  const [fleetName, setFleetName] = useState<string | null>(null);
  const [clusterNumber, setClusterNumber] = useState<number | null>(null);
  const [showAnalytics, setShowAnalytics] = useState(false);

  if (showAnalytics) {
    return (
      <div className="app fleet">
        <main className="main">
          <nav className="fleet-crumbs">
            <button className="crumb" onClick={() => setShowAnalytics(false)}>
              Fleet
            </button>
            <span className="crumb current">Analytics</span>
            <span className="nimble-mono fleet-version">Argus Fleet v{version}</span>
          </nav>
          <Analytics token={token} />
        </main>
      </div>
    );
  }

  if (!view) {
    return (
      <div className="app fleet">
        <main className="main">
          <div className="section">
            <div className="nimble-glass--flat empty">
              <h3>{error ? "Cannot reach the control plane" : "Loading the fleet"}</h3>
              <p>
                {error
                  ? "Check the fleet URL and token, then retry."
                  : "Waiting for the first fleet view."}
              </p>
            </div>
          </div>
        </main>
      </div>
    );
  }

  const group = fleetName ? view.fleets.find((f) => f.name === fleetName) ?? null : null;
  const cluster =
    group && clusterNumber !== null
      ? group.clusters.find((c) => c.number === clusterNumber) ?? null
      : null;

  return (
    <div className="app fleet">
      <main className="main">
        <nav className="fleet-crumbs">
          <button
            className="crumb"
            onClick={() => {
              setFleetName(null);
              setClusterNumber(null);
            }}
          >
            Global
          </button>
          {group && (
            <button className="crumb" onClick={() => setClusterNumber(null)}>
              {group.name}
            </button>
          )}
          {cluster && (
            <span className="crumb current">
              #{cluster.number}
            </span>
          )}
          {analyticsEnabled && (
            <button className="crumb" onClick={() => setShowAnalytics(true)}>
              Analytics
            </button>
          )}
          <span className="nimble-mono fleet-version">Argus Fleet v{version}</span>
        </nav>

        {cluster && group ? (
          <Cluster cluster={cluster} fleet={group.name} token={token} />
        ) : group ? (
          <Fleet group={group} onCluster={setClusterNumber} />
        ) : (
          <Global view={view} onFleet={setFleetName} />
        )}
      </main>
    </div>
  );
}
