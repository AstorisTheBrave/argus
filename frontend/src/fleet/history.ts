// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { useEffect, useState } from "react";

export interface TrendPoint {
  t: string;
  metrics: Record<string, number>;
}

// Extract one metric key's values across the recorded points (missing -> 0).
export function seriesFor(history: TrendPoint[], key: string): number[] {
  return history.map((p) => p.metrics[key] ?? 0);
}

// Poll one cluster's recent history for the drill-down sparklines.
export function useClusterHistory(
  token: string | null,
  fleet: string,
  number: number,
  intervalMs = 5000,
) {
  const [history, setHistory] = useState<TrendPoint[]>([]);

  useEffect(() => {
    let stop = false;
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const url = `/api/fleet/cluster?fleet=${encodeURIComponent(fleet)}&number=${number}`;

    async function tick() {
      try {
        const resp = await fetch(url, { headers });
        if (!resp.ok) return;
        const data = await resp.json();
        if (!stop) setHistory(Array.isArray(data.history) ? data.history : []);
      } catch {
        // Best-effort: leave the last history in place on a transient error.
      }
    }

    tick();
    const handle = window.setInterval(tick, intervalMs);
    return () => {
      stop = true;
      window.clearInterval(handle);
    };
  }, [token, fleet, number, intervalMs]);

  return history;
}
