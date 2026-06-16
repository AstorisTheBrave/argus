# argus-dpy

Operational Prometheus / OpenTelemetry metrics for [discord.py](https://github.com/Rapptz/discord.py) bots, in one line.

```python
from argus import Argus

Argus(bot)  # serves /metrics on the bot's event loop
```

Argus instruments shard latency, interaction/command throughput and outcomes,
command duration, gateway events and rate-limit pressure, then exposes them as a
Prometheus endpoint running inside the bot's own asyncio loop. It is backend
agnostic at the core, ships Grafana dashboards and a compose stack, and never
puts a guild, user, or channel id on a metric label.

> Status: alpha, under active construction.

## Install

```bash
pip install argus-dpy
```

## License

MIT
