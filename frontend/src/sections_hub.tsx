// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { useCallback, useEffect, useState } from "react";

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

const GRAFANA_BOARDS: [string, string][] = [
  ["Overview", "argus-overview"],
  ["Interactions", "argus-interactions"],
  ["Gateway", "argus-gateway"],
];

export function Grafana({ grafanaUrl }: { grafanaUrl: string | null }) {
  const [board, setBoard] = useState("argus-overview");
  if (!grafanaUrl) {
    return (
      <EmptyState
        title="Grafana not configured"
        hint="Pass grafana_url to Argus(bot) to embed your dashboards here."
      />
    );
  }
  const base = grafanaUrl.replace(/\/$/, "");
  return (
    <div className="section grafana-section">
      <div className="grafana-tabs">
        {GRAFANA_BOARDS.map(([label, uid]) => (
          <button
            key={uid}
            className={uid === board ? "grafana-tab active" : "grafana-tab"}
            onClick={() => setBoard(uid)}
          >
            {label}
          </button>
        ))}
        <a className="grafana-open" href={`${base}/d/${board}`} target="_blank" rel="noreferrer">
          Open in Grafana ↗
        </a>
      </div>
      <iframe className="grafana-frame" title="Grafana" src={`${base}/d/${board}?kiosk`} />
    </div>
  );
}

interface AnalyticsRow {
  rows: (string | number)[][];
}

export function Analytics({ enabled, token }: { enabled: boolean; token: string | null }) {
  const [guildId, setGuildId] = useState("demo-guild-1");
  const [volume, setVolume] = useState<(string | number)[][]>([]);
  const [commands, setCommands] = useState<(string | number)[][]>([]);
  const [avgMs, setAvgMs] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const get = async (path: string) => {
      const r = await fetch(`/api/analytics/${path}?guild_id=${encodeURIComponent(guildId)}`, {
        headers,
      });
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    };
    try {
      const [vol, cmd, avg] = await Promise.all([
        get("interaction-volume") as Promise<AnalyticsRow>,
        get("command-stats") as Promise<AnalyticsRow>,
        get("avg-duration") as Promise<{ avg_ms: number }>,
      ]);
      setVolume(vol.rows);
      setCommands(cmd.rows);
      setAvgMs(avg.avg_ms);
    } catch (e) {
      setError(`request failed (${e instanceof Error ? e.message : "error"})`);
    }
  }, [guildId, token]);

  // Load once on mount so the tab shows data immediately when analytics is on.
  useEffect(() => {
    if (enabled && guildId) void load();
    // Only auto-load on first render; further loads are user-driven.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  if (!enabled) {
    return (
      <EmptyState
        title="Analytics off"
        hint="Set enable_per_guild and clickhouse_dsn (with a dashboard_auth_token) to enable per-guild analytics."
      />
    );
  }

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
      {avgMs !== null && (
        <div className="grid">
          <div className="nimble-glass--flat stat">
            <div className="label">Avg command duration</div>
            <div className="value nimble-mono">
              {avgMs.toFixed(1)}
              <span className="unit"> ms</span>
            </div>
          </div>
        </div>
      )}
      <table className="nimble-glass--flat analytics-table">
        <thead>
          <tr>
            <th>command</th>
            <th>count</th>
            <th>avg ms</th>
          </tr>
        </thead>
        <tbody>
          {commands.map((row, i) => (
            <tr key={i}>
              <td className="nimble-mono">{String(row[0])}</td>
              <td className="nimble-mono">{String(row[1])}</td>
              <td className="nimble-mono">{Number(row[2]).toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
