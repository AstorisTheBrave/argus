// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { useCallback, useEffect, useRef, useState } from "react";

import type { Snapshot } from "./lib/prom";
import { subscribeSnapshots } from "./lib/snapshot";

export interface DashConfig {
  namespace: string;
  metrics_path: string;
  grafana_url: string | null;
  analytics_enabled: boolean;
  version: string;
  auth_required: boolean;
}

export interface Frame {
  t: number;
  snap: Snapshot;
}

const MAX_FRAMES = 120;
const TOKEN_KEY = "argus_token";

function initialToken(): string | null {
  // A ?token= in the URL is remembered, so a shared dashboard link only needs
  // the token once.
  const fromUrl = new URLSearchParams(window.location.search).get("token");
  if (fromUrl) {
    window.localStorage.setItem(TOKEN_KEY, fromUrl);
    return fromUrl;
  }
  return window.localStorage.getItem(TOKEN_KEY);
}

export function useDashboard() {
  const [token, setTokenState] = useState<string | null>(initialToken);
  const [config, setConfig] = useState<DashConfig | null>(null);
  const [authError, setAuthError] = useState(false);
  const [frames, setFrames] = useState<Frame[]>([]);
  const tokenRef = useRef(token);
  tokenRef.current = token;

  const setToken = useCallback((value: string) => {
    window.localStorage.setItem(TOKEN_KEY, value);
    setTokenState(value);
    setAuthError(false);
  }, []);

  useEffect(() => {
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    fetch("/api/config", { headers })
      .then((r) => {
        if (r.status === 401) {
          setAuthError(true);
          return null;
        }
        return r.json();
      })
      .then((data) => data && setConfig(data as DashConfig))
      .catch(() => undefined);
  }, [token]);

  useEffect(() => {
    const unsubscribe = subscribeSnapshots(
      (snap) => setFrames((prev) => [...prev.slice(-(MAX_FRAMES - 1)), { t: Date.now(), snap }]),
      { token },
    );
    return unsubscribe;
  }, [token]);

  const latest = frames.length > 0 ? frames[frames.length - 1].snap : null;
  return { config, frames, latest, token, setToken, authError };
}
