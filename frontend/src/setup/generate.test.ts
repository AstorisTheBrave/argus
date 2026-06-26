import { describe, expect, it } from "vitest";

import { defaultChoices, generate, sanitizeNamespace, type SetupChoices } from "./generate";

function choices(overrides: Partial<SetupChoices> = {}): SetupChoices {
  return { ...defaultChoices, ...overrides };
}

function file(out: ReturnType<typeof generate>, name: string): string {
  const f = out.files.find((x) => x.name === name);
  if (!f) throw new Error(`expected a ${name} file, got ${out.files.map((x) => x.name).join(", ")}`);
  return f.content;
}

describe("sanitizeNamespace", () => {
  it("lowercases and replaces invalid characters with underscores", () => {
    expect(sanitizeNamespace("My Cool Bot!")).toBe("my_cool_bot");
  });

  it("falls back to discord when nothing usable remains", () => {
    expect(sanitizeNamespace("  !!! ")).toBe("discord");
    expect(sanitizeNamespace("")).toBe("discord");
  });
});

describe("generate (docker, defaults)", () => {
  const out = generate(choices());

  it("emits the docker file set", () => {
    expect(out.files.map((f) => f.name).sort()).toEqual(
      [".env", "Dockerfile", "bot.py", "docker-compose.yml", "requirements.txt"].sort(),
    );
  });

  it("writes a token placeholder when none was entered", () => {
    expect(file(out, ".env")).toContain("DISCORD_TOKEN=paste-your-discord-bot-token-here");
  });

  it("requires only the dotenv extra by default", () => {
    expect(file(out, "requirements.txt").trim()).toBe("argus-dpy[dotenv]");
  });

  it("maps the env file into the container and exposes the dashboard port", () => {
    const compose = file(out, "docker-compose.yml");
    expect(compose).toContain("env_file: .env");
    expect(compose).toContain("9191:9191");
  });
});

describe("generate (feature toggles)", () => {
  it("includes analytics extras, env vars and a DSN placeholder", () => {
    const out = generate(choices({ analytics: true }));
    expect(file(out, "requirements.txt")).toContain("clickhouse");
    const env = file(out, ".env");
    expect(env).toContain("ARGUS_ENABLE_PER_GUILD=1");
    expect(env).toContain("ARGUS_CLICKHOUSE_DSN=");
  });

  it("includes tracing extras and endpoint", () => {
    const out = generate(choices({ tracing: true, tracingEndpoint: "http://otel:4317" }));
    expect(file(out, "requirements.txt")).toContain("otlp");
    expect(file(out, ".env")).toContain("ARGUS_TRACING_ENDPOINT=http://otel:4317");
  });

  it("disables the dashboard and drops the published port", () => {
    const out = generate(choices({ dashboard: false }));
    expect(file(out, ".env")).toContain("ARGUS_DASHBOARD=0");
    expect(file(out, "docker-compose.yml")).not.toContain("ports:");
  });

  it("writes the dashboard password only when the dashboard is on", () => {
    expect(file(generate(choices({ dashboardPassword: "s3cret" })), ".env")).toContain(
      "ARGUS_DASHBOARD_AUTH_TOKEN=s3cret",
    );
    expect(
      file(generate(choices({ dashboard: false, dashboardPassword: "s3cret" })), ".env"),
    ).not.toContain("ARGUS_DASHBOARD_AUTH_TOKEN");
  });

  it("sanitizes the namespace into the env file", () => {
    expect(file(generate(choices({ namespace: "Cool Bot" })), ".env")).toContain(
      "ARGUS_NAMESPACE=cool_bot",
    );
  });
});

describe("generate (token confinement)", () => {
  it("writes the token only into .env, never into other files or steps", () => {
    const token = "super-secret-token-value";
    const out = generate(choices({ token, host: "docker" }));
    for (const f of out.files) {
      if (f.name === ".env") expect(f.content).toContain(token);
      else expect(f.content).not.toContain(token);
    }
    for (const step of out.steps) expect(step).not.toContain(token);
  });
});

describe("generate (host targets)", () => {
  it("docker emits a Dockerfile and compose", () => {
    const names = generate(choices({ host: "docker" })).files.map((f) => f.name);
    expect(names).toContain("Dockerfile");
    expect(names).toContain("docker-compose.yml");
  });

  it("railway emits railway.json", () => {
    expect(generate(choices({ host: "railway" })).files.map((f) => f.name)).toContain("railway.json");
  });

  it("pterodactyl and local emit only the core files", () => {
    for (const host of ["pterodactyl", "local"] as const) {
      const names = generate(choices({ host })).files.map((f) => f.name).sort();
      expect(names).toEqual([".env", "bot.py", "requirements.txt"].sort());
    }
  });

  it("produces non-empty, host-specific steps for every target", () => {
    for (const host of ["docker", "railway", "pterodactyl", "local"] as const) {
      const steps = generate(choices({ host })).steps;
      expect(steps.length).toBeGreaterThan(2);
    }
  });
});
