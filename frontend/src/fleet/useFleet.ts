// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { useEffect, useState } from "react";

import type { FleetView } from "./types";

// Poll the fleet view. The control plane has no SSE stream; a short interval
// poll keeps the grid live without holding a connection open per viewer.
export function useFleet(token: string | null, intervalMs = 5000) {
  const [view, setView] = useState<FleetView | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let stop = false;
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

    async function tick() {
      try {
        const resp = await fetch("/api/fleet/view", { headers });
        if (!resp.ok) {
          setError(true);
          return;
        }
        const data = (await resp.json()) as FleetView;
        if (!stop) {
          setView(data);
          setError(false);
        }
      } catch {
        if (!stop) setError(true);
      }
    }

    tick();
    const handle = window.setInterval(tick, intervalMs);
    return () => {
      stop = true;
      window.clearInterval(handle);
    };
  }, [token, intervalMs]);

  return { view, error };
}
