// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

// A small Prometheus text-exposition parser. Produces the same Snapshot shape
// the SSE endpoint sends as JSON, so the UI consumes one model regardless of
// transport.

export interface Sample {
  name: string;
  labels: Record<string, string>;
  value: number;
}

export interface Family {
  type: string;
  samples: Sample[];
}

export interface Snapshot {
  metrics: Record<string, Family>;
}

const LABEL_RE = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"\\])*)"/g;

function parseValue(raw: string): number {
  const token = raw.trim().split(/\s+/)[0];
  if (token === "+Inf") return Infinity;
  if (token === "-Inf") return -Infinity;
  return Number(token);
}

function parseLabels(block: string | undefined): Record<string, string> {
  const labels: Record<string, string> = {};
  if (!block) return labels;
  let match: RegExpExecArray | null;
  LABEL_RE.lastIndex = 0;
  while ((match = LABEL_RE.exec(block)) !== null) {
    labels[match[1]] = match[2].replace(/\\"/g, '"').replace(/\\\\/g, "\\").replace(/\\n/g, "\n");
  }
  return labels;
}

export function parsePrometheus(text: string): Snapshot {
  const families: Record<string, Family> = {};
  const types: Array<[string, string]> = [];

  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (trimmed === "") continue;
    if (trimmed.startsWith("# TYPE ")) {
      const parts = trimmed.split(/\s+/); // ["#", "TYPE", <name>, <type>]
      const name = parts[2];
      const type = parts[3];
      families[name] = { type, samples: [] };
      types.push([name, type]);
      continue;
    }
    if (trimmed.startsWith("#")) continue;

    const m = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{(.*)\})?\s+(.+)$/.exec(trimmed);
    if (!m) continue;
    const sample: Sample = { name: m[1], labels: parseLabels(m[3]), value: parseValue(m[4]) };

    // Assign to the longest declared family name that prefixes the sample name.
    let owner = "";
    for (const [fam] of types) {
      if ((sample.name === fam || sample.name.startsWith(fam + "_")) && fam.length > owner.length) {
        owner = fam;
      }
    }
    if (owner === "") {
      owner = sample.name;
      families[owner] ??= { type: "untyped", samples: [] };
    }
    families[owner].samples.push(sample);
  }

  return { metrics: families };
}
