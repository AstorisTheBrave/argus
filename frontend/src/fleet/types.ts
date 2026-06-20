// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

export type Health = "up" | "down";

export interface ClusterView {
  number: number;
  identity: string;
  fleet: string;
  status: Health;
  last_seen: string;
  metrics: Record<string, number>;
}

export interface FleetGroupView {
  name: string;
  clusters_up: number;
  clusters_total: number;
  rollup: Record<string, number>;
  clusters: ClusterView[];
}

export interface FleetView {
  generated_at: string;
  global: Record<string, number>;
  fleets: FleetGroupView[];
}
