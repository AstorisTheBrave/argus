# Threat model

How Argus can be attacked or misused, and what stops it. This complements
[SECURITY.md](SECURITY.md) (how to report a vulnerability) and the production
hardening already in the code. It is scoped to what Argus ships: an in-process
SDK embedded in a discord.py bot, an optional standalone fleet control plane, and
a bundled dashboard SPA. The user's bot logic, Discord itself, and the user's
Prometheus/Grafana/ClickHouse deployments are out of scope.

## Assets

- **Bot availability.** The single most important asset. Argus must never be the
  reason a bot crashes or stalls.
- **Operational metrics** (`/metrics`, the dashboard). Aggregate, non-PII counts
  and gauges.
- **Per-guild analytical events** (optional ClickHouse path). More sensitive:
  they carry `guild_id`. Never exposed via Prometheus.
- **Credentials.** The dashboard auth token, fleet ingest/viewer tokens, and the
  per-identity lease secret.
- **Fleet registry state.** The control plane's view of which clusters exist.

## Trust boundaries

1. **The bot process <-> Argus instrumentation.** Argus runs in the bot's event
   loop. A bug here can take the bot down.
2. **The network <-> the in-process HTTP server** (`/metrics`, dashboard, SSE).
   Open by default for scraping.
3. **A member bot <-> the fleet control plane** (register/heartbeat ingest).
4. **An operator's browser <-> the fleet/dashboard read APIs.**
5. **The build/release pipeline <-> PyPI and GHCR** (supply chain).

## Threats and mitigations

### T1 - Instrumentation crashes or stalls the bot (boundary 1)
- **Spoiler: this is the headline guarantee.** Every hook body runs inside a
  fail-open wrapper that counts and swallows errors
  (`argus_instrumentation_errors_total`) and never raises into the loop
  (invariant 5). Hooks are O(1) and do no I/O or awaits on the hot path
  (invariant 3). A metrics server that cannot bind is caught at startup, marked
  via `argus_subsystem_up{subsystem="server"}=0`, and the bot runs on. A single
  failing scrape-time gauge callback is isolated and skipped rather than failing
  the whole `/metrics` response. Memory is bounded (capped in-flight timer maps;
  a bounded, lossy analytical queue).

### T2 - Unauthenticated read of operational data (boundary 2)
- `/metrics` and the dashboard expose **aggregate, non-PII** data; `/metrics`
  must stay open for Prometheus. The dashboard can be gated with
  `dashboard_auth_token` (constant-time compare); if it binds off-loopback with
  no token, Argus logs a warning pointing at the fix. For anything public, bind
  to loopback and reverse-proxy, or set a token.

### T3 - PII / high-cardinality leakage (boundary 2)
- `guild_id`/`user_id`/`channel_id` are **never** Prometheus labels, enforced by
  a test, not convention (invariant 2). All operational labels are drawn from
  bounded sets; unknown inputs collapse to `unknown`, so a hostile command name
  cannot explode cardinality. The per-guild analytical path is separate, carries
  `guild_id` only in ClickHouse, and fails closed without a token (invariant 7).

### T4 - Resource exhaustion on the HTTP surface (boundaries 2, 4)
- Request bodies are capped; the SSE stream caps concurrent connections and
  shares a cached snapshot across viewers. The fleet plane rate-limits reads and
  writes (per IP and per identity, 429) and caps registered clusters.

### T5 - Forged or hijacked fleet membership (boundary 3)
- The fleet plane refuses to start on a public bind without a token. Ingest and
  viewer tokens are split so a leaked bot token cannot read the dashboard, and
  any token accepts a comma-separated list for zero-downtime rotation. With
  `require_lease`, a per-identity high-entropy secret (stored only as an
  HMAC-SHA256 digest, optionally peppered, verified constant-time) stops even a
  leaked ingest token from taking over an existing cluster's slot. Duplicate
  identities are detected and counted; an optional audit log records ingest
  events.

### T6 - Log injection / fingerprinting (boundaries 2, 4)
- Untrusted values written to logs are stripped of CR/LF and truncated. The
  `Server` version banner is stripped and security headers
  (`X-Frame-Options`, `X-Content-Type-Options`, CSP, `Referrer-Policy`) are sent
  on every response, on both the bot server and the fleet plane.

### T7 - Supply-chain compromise (boundary 5)
- PyPI releases use OIDC Trusted Publishing with attestations (no long-lived
  credentials). A CycloneDX SBOM of the wheel is attached to each GitHub release;
  the container images ship their own SBOM and max-provenance attestation. CI
  runs CodeQL, a `pip-audit` dependency audit, and Dependabot.

## Residual risks / non-goals

- Argus does not provide TLS; terminate it at a reverse proxy or tunnel. Tokens
  are bearer credentials and must travel over TLS in production.
- There is no per-user RBAC: surfaces are gated by machine/operator tokens, which
  is the intended depth for this tool (see the production-readiness standard).
- A determined operator who sets no token and binds the dashboard to a public
  interface exposes aggregate data; Argus warns but cannot refuse (that would
  also close `/metrics`).
- Argus trusts the bot object it is given; a malicious in-process bot is already
  past every boundary that matters.
