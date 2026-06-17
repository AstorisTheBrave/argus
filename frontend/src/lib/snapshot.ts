// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

// Live snapshot subscription: prefer the SSE stream, fall back to polling the
// metrics text endpoint. Both resolve to the same Snapshot shape.

import { parsePrometheus, type Snapshot } from "./prom";

export type SnapshotHandler = (snapshot: Snapshot) => void;

export interface SubscribeOptions {
  token?: string | null;
  metricsPath?: string;
  intervalMs?: number;
}

export function subscribeSnapshots(onSnapshot: SnapshotHandler, opts: SubscribeOptions = {}): () => void {
  const { token, metricsPath = "/metrics", intervalMs = 5000 } = opts;
  let source: EventSource | null = null;
  let timer: ReturnType<typeof setInterval> | null = null;
  let stopped = false;

  const startPolling = () => {
    if (timer !== null) return;
    const poll = async () => {
      try {
        const response = await fetch(metricsPath);
        if (response.ok) onSnapshot(parsePrometheus(await response.text()));
      } catch {
        // transient; next tick retries
      }
    };
    void poll();
    timer = setInterval(() => void poll(), intervalMs);
  };

  try {
    const url = token ? `/api/stream?token=${encodeURIComponent(token)}` : "/api/stream";
    source = new EventSource(url);
    source.onmessage = (event) => {
      try {
        onSnapshot(JSON.parse(event.data) as Snapshot);
      } catch {
        // ignore malformed frame
      }
    };
    source.onerror = () => {
      if (stopped) return;
      source?.close();
      source = null;
      startPolling();
    };
  } catch {
    startPolling();
  }

  return () => {
    stopped = true;
    source?.close();
    if (timer !== null) clearInterval(timer);
  };
}
