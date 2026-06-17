// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { useState } from "react";

function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="section">
      <div className="nimble-glass--flat empty">
        <h3>{title}</h3>
        <p>{hint}</p>
      </div>
    </div>
  );
}

export function Grafana({ grafanaUrl }: { grafanaUrl: string | null }) {
  if (!grafanaUrl) {
    return (
      <EmptyState
        title="Grafana not configured"
        hint="Pass grafana_url to Argus(bot) to link and embed your dashboards here."
      />
    );
  }
  const base = grafanaUrl.replace(/\/$/, "");
  const boards: [string, string][] = [
    ["Overview", "argus-overview"],
    ["Interactions", "argus-interactions"],
    ["Gateway", "argus-gateway"],
  ];
  return (
    <div className="section">
      <div className="links">
        {boards.map(([label, uid]) => (
          <a
            key={uid}
            className="nimble-glass--flat link"
            href={`${base}/d/${uid}`}
            target="_blank"
            rel="noreferrer"
          >
            {label} dashboard
          </a>
        ))}
      </div>
      <iframe className="grafana-frame" title="Grafana" src={`${base}/d/argus-overview?kiosk`} />
    </div>
  );
}

interface AnalyticsRow {
  rows: (string | number)[][];
}

export function Analytics({ enabled, token }: { enabled: boolean; token: string | null }) {
  const [guildId, setGuildId] = useState("");
  const [volume, setVolume] = useState<(string | number)[][]>([]);
  const [error, setError] = useState("");

  if (!enabled) {
    return (
      <EmptyState
        title="Analytics off"
        hint="Set enable_per_guild and clickhouse_dsn (with a dashboard_auth_token) to enable per-guild analytics."
      />
    );
  }

  const load = async () => {
    setError("");
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    try {
      const r = await fetch(
        `/api/analytics/interaction-volume?guild_id=${encodeURIComponent(guildId)}`,
        { headers },
      );
      if (!r.ok) {
        setError(`request failed (${r.status})`);
        return;
      }
      const data = (await r.json()) as AnalyticsRow;
      setVolume(data.rows);
    } catch {
      setError("request failed");
    }
  };

  return (
    <div className="section">
      <div className="analytics-controls">
        <input
          className="nimble-glass--flat"
          placeholder="guild id"
          value={guildId}
          onChange={(e) => setGuildId(e.target.value)}
        />
        <button className="nimble-glass--flat" onClick={() => void load()} disabled={!guildId}>
          Load
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <table className="nimble-glass--flat analytics-table">
        <thead>
          <tr>
            <th>day</th>
            <th>interactions</th>
          </tr>
        </thead>
        <tbody>
          {volume.map((row, i) => (
            <tr key={i}>
              <td className="nimble-mono">{String(row[0])}</td>
              <td className="nimble-mono">{String(row[1])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
