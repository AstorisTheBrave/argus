import { describe, expect, it } from "vitest";

import { parsePrometheus } from "./prom";

const TEXT = `# HELP discord_guilds Number of guilds.
# TYPE discord_guilds gauge
discord_guilds{cluster="default"} 3.0
# TYPE discord_interactions counter
discord_interactions_total{type="application_command",status="received"} 7.0
discord_interactions_created{type="application_command",status="received"} 1.7e9
# TYPE discord_shard_latency_seconds gauge
discord_shard_latency_seconds{shard="0"} 0.1
`;

describe("parsePrometheus", () => {
  it("parses a gauge sample with labels and value", () => {
    const snap = parsePrometheus(TEXT);
    const g = snap.metrics["discord_guilds"];
    expect(g.type).toBe("gauge");
    expect(g.samples[0].labels).toEqual({ cluster: "default" });
    expect(g.samples[0].value).toBe(3);
  });

  it("groups _total and _created under the counter family", () => {
    const snap = parsePrometheus(TEXT);
    const c = snap.metrics["discord_interactions"];
    expect(c.type).toBe("counter");
    const names = c.samples.map((s) => s.name).sort();
    expect(names).toEqual(["discord_interactions_created", "discord_interactions_total"]);
  });

  it("assigns to the longest matching family name", () => {
    const snap = parsePrometheus(TEXT);
    // discord_shard_latency_seconds must not be swallowed by a shorter family.
    expect(snap.metrics["discord_shard_latency_seconds"].samples[0].value).toBe(0.1);
  });
});
