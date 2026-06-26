// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

// The no-code setup wizard: a few plain-language questions that produce a
// ready-to-run Argus setup. Everything is generated in the browser (see
// generate.ts) -- the bot token never leaves the page.

import { useMemo, useState } from "react";

import "./setup.css";
import {
  defaultChoices,
  generate,
  type GeneratedFile,
  type HostTarget,
  type SetupChoices,
} from "./generate";

const HOSTS: { id: HostTarget; title: string; blurb: string }[] = [
  { id: "docker", title: "Docker", blurb: "Run anywhere with one command. Easiest if unsure." },
  { id: "railway", title: "Railway", blurb: "Managed cloud host, deploy from the web." },
  { id: "pterodactyl", title: "Game/bot panel", blurb: "Pterodactyl, PebbleHost and similar." },
  { id: "local", title: "My own computer / VPS", blurb: "Plain Python, you manage it." },
];

// Each entry is one screen in the funnel; the last (result) is rendered apart.
const INPUT_STEPS = ["welcome", "token", "basics", "features", "host"] as const;

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="setup-toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <span className="setup-toggle-label">{label}</span>
        {hint ? <span className="setup-hint">{hint}</span> : null}
      </span>
    </label>
  );
}

function Field({
  label,
  hint,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="setup-field">
      <span className="setup-toggle-label">{label}</span>
      {hint ? <span className="setup-hint">{hint}</span> : null}
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

function FileCard({ file }: { file: GeneratedFile }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    void navigator.clipboard?.writeText(file.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const download = () => {
    const blob = new Blob([file.content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.name;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="nimble-glass--flat setup-file">
      <div className="setup-file-head">
        <span className="setup-file-name">{file.name}</span>
        <span className="setup-file-actions">
          <button type="button" onClick={copy}>
            {copied ? "Copied" : "Copy"}
          </button>
          <button type="button" onClick={download}>
            Download
          </button>
        </span>
      </div>
      <pre className="setup-code">
        <code>{file.content}</code>
      </pre>
    </div>
  );
}

export function SetupWizard() {
  const [step, setStep] = useState(0);
  const [choices, setChoices] = useState<SetupChoices>(defaultChoices);
  const output = useMemo(() => generate(choices), [choices]);

  const set = <K extends keyof SetupChoices>(key: K, value: SetupChoices[K]) =>
    setChoices((c) => ({ ...c, [key]: value }));

  const onResult = step >= INPUT_STEPS.length;
  const current = INPUT_STEPS[step];

  const downloadAll = () => {
    // Sequential anchor clicks; a small stagger keeps browsers from collapsing
    // them into a single prompt.
    output.files.forEach((file, i) => {
      setTimeout(() => {
        const url = URL.createObjectURL(new Blob([file.content], { type: "text/plain" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = file.name;
        a.click();
        URL.revokeObjectURL(url);
      }, i * 250);
    });
  };

  return (
    <div className="setup-screen">
      <div className="setup-shell">
        <header className="setup-head">
          <div className="brand">
            <span className="brand-dot" />
            Argus setup
          </div>
          {!onResult ? (
            <span className="setup-progress">
              Step {step + 1} of {INPUT_STEPS.length}
            </span>
          ) : null}
        </header>

        <div className="nimble-glass setup-card">
          {current === "welcome" ? (
            <section className="setup-section">
              <h2>Get your bot monitored, no coding required</h2>
              <p>
                Answer a few questions and Argus builds every file you need to run a Discord bot
                with live metrics and a dashboard. Nothing you type here is uploaded -- your bot
                token stays in this browser.
              </p>
            </section>
          ) : null}

          {current === "token" ? (
            <section className="setup-section">
              <h2>Your bot token</h2>
              <Field
                label="Discord bot token (optional)"
                hint="From the Discord Developer Portal. You can leave this blank and paste it into the .env later. It is never sent anywhere."
                type="password"
                value={choices.token}
                placeholder="paste here, or skip"
                onChange={(v) => set("token", v)}
              />
            </section>
          ) : null}

          {current === "basics" ? (
            <section className="setup-section">
              <h2>The basics</h2>
              <Field
                label="A short name for your bot"
                hint="Used as the metric prefix. Letters, numbers and underscores."
                value={choices.namespace}
                placeholder="discord"
                onChange={(v) => set("namespace", v)}
              />
              <Toggle
                label="Show a live dashboard"
                hint="A web page with your bot's metrics. Recommended."
                checked={choices.dashboard}
                onChange={(v) => set("dashboard", v)}
              />
              {choices.dashboard ? (
                <Field
                  label="Dashboard password (optional)"
                  hint="Leave blank only if the dashboard is on a private network."
                  type="password"
                  value={choices.dashboardPassword}
                  placeholder="a password to open the dashboard"
                  onChange={(v) => set("dashboardPassword", v)}
                />
              ) : null}
            </section>
          ) : null}

          {current === "features" ? (
            <section className="setup-section">
              <h2>Extra features</h2>
              <Toggle
                label="Per-server analytics"
                hint="Track usage per Discord server. Needs a ClickHouse database."
                checked={choices.analytics}
                onChange={(v) => set("analytics", v)}
              />
              {choices.analytics ? (
                <Field
                  label="ClickHouse connection string"
                  value={choices.clickhouseDsn}
                  placeholder="clickhouse://user:pass@host:8123/db"
                  onChange={(v) => set("clickhouseDsn", v)}
                />
              ) : null}
              <Toggle
                label="Send traces to a collector"
                hint="Advanced: one OpenTelemetry span per command."
                checked={choices.tracing}
                onChange={(v) => set("tracing", v)}
              />
              {choices.tracing ? (
                <Field
                  label="Collector endpoint"
                  value={choices.tracingEndpoint}
                  placeholder="http://your-collector:4317"
                  onChange={(v) => set("tracingEndpoint", v)}
                />
              ) : null}
            </section>
          ) : null}

          {current === "host" ? (
            <section className="setup-section">
              <h2>Where will you run it?</h2>
              <div className="setup-hosts">
                {HOSTS.map((h) => (
                  <button
                    key={h.id}
                    type="button"
                    className={`setup-host${choices.host === h.id ? " selected" : ""}`}
                    onClick={() => set("host", h.id)}
                  >
                    <span className="setup-toggle-label">{h.title}</span>
                    <span className="setup-hint">{h.blurb}</span>
                  </button>
                ))}
              </div>
            </section>
          ) : null}

          {onResult ? (
            <section className="setup-section">
              <h2>You're ready</h2>
              <ol className="setup-steps">
                {output.steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ol>
              <div className="setup-files">
                {output.files.map((f) => (
                  <FileCard key={f.name} file={f} />
                ))}
              </div>
            </section>
          ) : null}
        </div>

        <footer className="setup-foot">
          {step > 0 ? (
            <button type="button" className="setup-secondary" onClick={() => setStep((s) => s - 1)}>
              Back
            </button>
          ) : (
            <span />
          )}
          {!onResult ? (
            <button type="button" className="setup-primary" onClick={() => setStep((s) => s + 1)}>
              {step === 0 ? "Start" : current === "host" ? "Generate my setup" : "Next"}
            </button>
          ) : (
            <button type="button" className="setup-primary" onClick={downloadAll}>
              Download all files
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
