// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

import { Activity, BarChart3, Database, Radio, Zap, type LucideIcon } from "lucide-react";
import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";

export type SectionId = "overview" | "interactions" | "gateway" | "grafana" | "analytics";

export const SECTIONS: { id: SectionId; label: string; icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", icon: Activity },
  { id: "interactions", label: "Interactions", icon: Zap },
  { id: "gateway", label: "Gateway", icon: Radio },
  { id: "grafana", label: "Grafana", icon: BarChart3 },
  { id: "analytics", label: "Analytics", icon: Database },
];

export function Sidebar(props: {
  active: SectionId;
  onSelect: (id: SectionId) => void;
  clusters: string[];
  cluster: string;
  onCluster: (c: string) => void;
  version: string;
}) {
  return (
    <nav className="nimble-glass sidebar">
      <div className="brand">
        <span className="brand-dot" />
        <span>Argus</span>
      </div>
      <ul>
        {SECTIONS.map(({ id, label, icon: Icon }) => (
          <li key={id}>
            <button
              className={id === props.active ? "nav-item active" : "nav-item"}
              onClick={() => props.onSelect(id)}
            >
              <Icon size={18} strokeWidth={1.75} />
              <span>{label}</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="sidebar-foot">
        {props.clusters.length > 1 && (
          <select value={props.cluster} onChange={(e) => props.onCluster(e.target.value)}>
            <option value="*">all clusters</option>
            {props.clusters.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
        <span className="nimble-mono version">v{props.version}</span>
      </div>
    </nav>
  );
}

export function StatCard({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="nimble-glass--flat stat">
      <div className="label">{label}</div>
      <div className="value nimble-mono">
        {value}
        {unit ? <span className="unit"> {unit}</span> : null}
      </div>
    </div>
  );
}

// A Grafana-style time-series panel: title + live value(s) in the header, a
// filled-area line chart below with gridlines and a bottom legend.
export function LineChart(props: {
  title: string;
  data: uPlot.AlignedData;
  series: { label: string; stroke: string }[];
  height?: number;
  unit?: string;
  format?: (n: number) => string;
}) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<uPlot | null>(null);
  const dataRef = useRef(props.data);
  dataRef.current = props.data;

  useEffect(() => {
    if (!host.current) return;
    const height = props.height ?? 190;
    const grid = { stroke: "rgba(255,255,255,0.05)", width: 1 };
    const opts: uPlot.Options = {
      width: host.current.clientWidth || 480,
      height,
      legend: { show: true },
      cursor: { points: { size: 6 } },
      scales: { x: { time: false } },
      axes: [
        { stroke: "#8a93a6", grid, ticks: { stroke: "rgba(255,255,255,0.05)" } },
        { stroke: "#8a93a6", grid, ticks: { stroke: "rgba(255,255,255,0.05)" }, size: 52 },
      ],
      series: [
        { label: "t" },
        ...props.series.map((s) => ({
          label: s.label,
          stroke: s.stroke,
          width: 2,
          points: { show: false },
          // Grafana-like soft area fill under each line.
          fill: (u: uPlot, seriesIdx: number) => {
            void seriesIdx;
            const g = u.ctx.createLinearGradient(0, 0, 0, height);
            g.addColorStop(0, s.stroke + "44");
            g.addColorStop(1, s.stroke + "00");
            return g;
          },
        })),
      ],
    };
    chart.current = new uPlot(opts, dataRef.current, host.current);
    const onResize = () => host.current && chart.current?.setSize({ width: host.current.clientWidth, height });
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.current?.destroy();
      chart.current = null;
    };
    // Create once; data updates flow through the effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    chart.current?.setData(props.data);
  }, [props.data]);

  // Latest value per series for the Grafana-style header readout.
  const fmt = props.format ?? ((n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2)));
  const lastValues = props.series.map((s, i) => {
    const col = props.data[i + 1] as (number | null | undefined)[] | undefined;
    const v = col && col.length > 0 ? col[col.length - 1] : null;
    return { label: s.label, stroke: s.stroke, value: v == null ? "-" : fmt(v) };
  });

  return (
    <div className="nimble-glass--flat panel">
      <div className="panel-head">
        <span className="panel-title">{props.title}</span>
        <span className="panel-readout">
          {lastValues.map((lv) => (
            <span key={lv.label} className="panel-value nimble-mono">
              <span className="panel-swatch" style={{ background: lv.stroke }} />
              {lv.value}
              {props.unit ? <span className="unit"> {props.unit}</span> : null}
            </span>
          ))}
        </span>
      </div>
      <div className="panel-body" ref={host} />
    </div>
  );
}
