// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { useState } from "react";

interface Rows {
  rows: (string | number)[][];
}

async function getJson<T>(url: string, token: string | null): Promise<T | null> {
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  try {
    const resp = await fetch(url, { headers });
    if (!resp.ok) return null;
    return (await resp.json()) as T;
  } catch {
    return null;
  }
}

// Per-guild analytics (ClickHouse), fleet-wide or scoped to one cluster/bot.
export function Analytics({ token }: { token: string | null }) {
  const [guild, setGuild] = useState("");
  const [cluster, setCluster] = useState("");
  const [top, setTop] = useState<(string | number)[][]>([]);
  const [avg, setAvg] = useState<number | null>(null);
  const [loaded, setLoaded] = useState(false);

  async function load(e: React.FormEvent) {
    e.preventDefault();
    if (!guild) return;
    const qs = `guild_id=${encodeURIComponent(guild)}${cluster ? `&cluster=${encodeURIComponent(cluster)}` : ""}`;
    const [t, a] = await Promise.all([
      getJson<Rows>(`/api/fleet/analytics/top-commands?${qs}`, token),
      getJson<{ avg_ms: number }>(`/api/fleet/analytics/avg-duration?${qs}`, token),
    ]);
    setTop(t?.rows ?? []);
    setAvg(a ? a.avg_ms : null);
    setLoaded(true);
  }

  return (
    <div className="section">
      <h2>Analytics</h2>
      <form className="analytics-controls" onSubmit={load}>
        <input
          value={guild}
          onChange={(e) => setGuild(e.target.value)}
          placeholder="guild id"
          aria-label="guild id"
        />
        <input
          value={cluster}
          onChange={(e) => setCluster(e.target.value)}
          placeholder="cluster (optional)"
          aria-label="cluster"
        />
        <button type="submit">Load</button>
      </form>

      {loaded && (
        <>
          <div className="grid">
            <div className="nimble-glass--flat stat">
              <div className="label">Avg command duration</div>
              <div className="value nimble-mono">{avg === null ? "-" : `${avg.toFixed(1)} ms`}</div>
            </div>
          </div>
          <h3>Top commands</h3>
          <table className="analytics-table">
            <thead>
              <tr>
                <th>Command</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {top.map((row) => (
                <tr key={String(row[0])}>
                  <td>{row[0]}</td>
                  <td className="nimble-mono">{row[1]}</td>
                </tr>
              ))}
              {top.length === 0 && (
                <tr>
                  <td colSpan={2} className="muted">
                    No data for this guild.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
