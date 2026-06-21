# Hosting Argus on Docker bot panels

Pterodactyl, PebbleHost, Ori, Railway and similar hosts run your bot in a
container with **limited inbound ports** and **varied config injection**. Argus
handles this, but the right setup depends on what your host allows. Use the
decision tree, then the matching recipe.

## Decision tree

1. **Can you reach an allocated port from outside?** (Pterodactyl/PebbleHost give
   you `SERVER_PORT`; Railway gives `PORT` + a generated domain.)
   - **Yes, and you run your own Prometheus** -> bind the allocation and scrape.
     Argus auto-detects the port, so usually you set nothing. See *Scrape*.
   - **No, or you'd rather not open a port** -> **push out**. This is the
     recommended path on locked-down hosts. See *Push*.
2. **Can you set environment variables in the panel?**
   - **Yes** -> set `ARGUS_*` variables directly.
   - **Only file uploads / a start command** -> upload a `.env` (install the
     `argus-dpy[dotenv]` extra so `Argus(bot)` loads it), or use
     [`start_shim.py`](start_shim.py) if you can't even set the start command.

## Push (recommended on locked hosts) — no inbound port

A Discord bot is outbound-only, and so are these. Pick one:

- **OTLP** to Grafana Cloud / any collector:
  ```bash
  ARGUS_OTLP_ENDPOINT=https://otlp.your-collector:4317 python bot.py
  ```
  (install `argus-dpy[otlp]`)
- **Fleet** — report to an Argus Fleet control plane on a VPS for a single pane
  across many bots:
  ```bash
  ARGUS_FLEET_URL=http://fleet-host:9190 ARGUS_FLEET_TOKEN=secret python bot.py
  ```

Neither needs an exposed port; both work through NAT.

## Scrape — bind the host's allocation

Argus resolves the port as `ARGUS_PORT -> SERVER_PORT -> PORT -> 9191` and the
host as `ARGUS_HOST -> SERVER_IP -> 0.0.0.0`, so on Pterodactyl/PebbleHost it
binds your primary allocation automatically. Then point Prometheus at
`node-ip:allocated-port`. **Set `ARGUS_DASHBOARD_AUTH_TOKEN`** if the port is
publicly reachable — an open dashboard on a shared node is an abuse surface.

## Per-host notes

| Host | Port | Config injection | Recipe |
|---|---|---|---|
| **Pterodactyl / PebbleHost** | `SERVER_PORT` (1 primary; more if the admin raises the allocation limit) | egg variables, or upload `.env` (FTP) | [`pterodactyl-egg.json`](pterodactyl-egg.json) |
| **Ori-class (start file only)** | a port exists but the panel is bare | upload `.env`; run [`start_shim.py`](start_shim.py) | shim + `.env` |
| **Railway** | bots need **no** port; for scrape bind `PORT` + *Generate Domain* | Variables tab / sealed secrets (no `.env` needed) | [`railway.json`](railway.json) |

## Security

A metrics/dashboard port exposed on a shared panel node can be hit by anyone who
reaches it. Prefer **push** (no port at all); if you must bind a public
allocation, set `ARGUS_DASHBOARD_AUTH_TOKEN` and treat the URL as a credential.
Argus already strips its version banner, sends security headers, caps the request
body, and bounds the SSE stream.
