// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

// A tiny dependency-free SVG sparkline. uPlot needs a canvas (unavailable in
// jsdom and overkill for a drill-down trend), so the trend lines are plain SVG.
export function Sparkline({
  values,
  width = 160,
  height = 36,
}: {
  values: number[];
  width?: number;
  height?: number;
}) {
  if (values.length < 2) {
    return <svg className="sparkline" width={width} height={height} aria-hidden="true" />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = width / (values.length - 1);
  const points = values
    .map((v, i) => {
      const x = i * stepX;
      // Invert y (SVG origin is top-left); pad 2px top/bottom.
      const y = height - 2 - ((v - min) / span) * (height - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="sparkline" width={width} height={height} aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
