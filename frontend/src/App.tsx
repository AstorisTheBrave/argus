// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { useState } from "react";

import "./app.css";
import { Sidebar, type SectionId } from "./components";
import { FleetApp } from "./fleet/FleetApp";
import { clusters } from "./lib/select";
import { Gateway, Interactions, Overview } from "./sections";
import { Analytics, Grafana } from "./sections_hub";
import { useDashboard } from "./useDashboard";

function TokenPrompt({ onSubmit }: { onSubmit: (t: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <div className="token-screen">
      <form
        className="nimble-glass token-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (value) onSubmit(value);
        }}
      >
        <h2>Authentication required</h2>
        <p>Enter the dashboard token.</p>
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="token" />
        <button type="submit">Continue</button>
      </form>
    </div>
  );
}

export function App() {
  const { config, latest, frames, token, setToken, authError } = useDashboard();
  const [active, setActive] = useState<SectionId>("overview");
  const [cluster, setCluster] = useState("*");

  if (authError && !token) {
    return <TokenPrompt onSubmit={setToken} />;
  }

  // The control plane serves the same bundle with config.fleet set; render the
  // multi-tier fleet view instead of the per-process dashboard.
  if (config?.fleet) {
    return (
      <FleetApp
        token={token}
        version={config.version}
        analyticsEnabled={config.analytics_enabled}
      />
    );
  }

  const clusterList = latest ? clusters(latest) : [];

  return (
    <div className="app">
      <Sidebar
        active={active}
        onSelect={setActive}
        clusters={clusterList}
        cluster={cluster}
        onCluster={setCluster}
        version={config?.version ?? ""}
      />
      <main className="main">
        {!latest ? (
          <div className="section">
            <div className="nimble-glass--flat empty">
              <h3>Waiting for the first sample</h3>
              <p>Argus is collecting metrics from your bot.</p>
            </div>
          </div>
        ) : active === "overview" ? (
          <Overview latest={latest} frames={frames} cluster={cluster} />
        ) : active === "interactions" ? (
          <Interactions latest={latest} frames={frames} />
        ) : active === "gateway" ? (
          <Gateway latest={latest} frames={frames} />
        ) : active === "grafana" ? (
          <Grafana grafanaUrl={config?.grafana_url ?? null} />
        ) : (
          <Analytics enabled={config?.analytics_enabled ?? false} token={token} />
        )}
      </main>
    </div>
  );
}
