# Argus — discord.py observability SDK
# Copyright (C) 2026 AstorisTheBrave
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""``python -m argus.fleet``: run the control plane, or scaffold and diagnose it.

Subcommands: ``run`` (default - serve), ``init`` (the setup wizard - write a
.env + compose + member snippet), ``doctor`` (probe a running control plane, or
check a bot host can reach it). On ``run`` a ``.env`` is autoloaded when
``python-dotenv`` is installed (the ``argus-dpy[fleet]`` extra); otherwise the
generated compose ``env_file`` / systemd ``EnvironmentFile`` loads it. Either
way ``FleetConfig.resolve`` still reads only the environment (invariant 6).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

from argus._logging import make_handler
from argus.exposition.server import start_server
from argus.fleet import doctor, wizard
from argus.fleet.config import FleetConfig
from argus.fleet.lock import StateLock
from argus.fleet.registry import Registry
from argus.fleet.server import build_fleet_app, ensure_secure_bind
from argus.fleet.sources.base import FleetDataSource
from argus.fleet.sources.composite import CompositeSource
from argus.fleet.sources.prometheus import PrometheusSource
from argus.fleet.sources.push import PushSource


def configure_logging(log_format: str) -> None:
    """Configure the service's root logging (text or json). Idempotent.

    Unlike the in-process SDK, the fleet plane is a standalone process, so it owns
    and replaces the root logger's handler (shared formatter via argus._logging).
    """
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(make_handler(log_format))
    root.setLevel(logging.INFO)


def build_source(config: FleetConfig) -> FleetDataSource:
    """Push only by default; Prometheus joined ahead of push when configured."""
    push = PushSource(config.namespace)
    if config.prometheus_url:
        prom = PrometheusSource(config.prometheus_url, config.namespace)
        return CompositeSource(prom, push)
    return push


async def build_analytics(config: FleetConfig) -> tuple[Any, Any]:
    """Build the analytics query layer + its client when a ClickHouse DSN is set.

    Returns ``(analytics, client)`` so the caller can close the client; both are
    ``None`` when analytics is not configured.
    """
    if not config.clickhouse_dsn:
        return None, None
    import clickhouse_connect  # type: ignore[import-not-found]

    from argus.history.query import AnalyticsQuery

    client = await clickhouse_connect.get_async_client(dsn=config.clickhouse_dsn)
    return AnalyticsQuery(client), client


def load_dotenv_if_available(environ: dict[str, str] | None = None) -> bool:
    """Soft-load a .env into the environment when python-dotenv is installed.

    Returns True if a file was loaded. No-op (returns False) when dotenv is not
    installed - the generated compose/systemd wiring loads it instead.
    """
    env = os.environ if environ is None else environ
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    path = env.get("ARGUS_FLEET_ENV_FILE") or ".env"
    if not Path(path).is_file():
        return False
    load_dotenv(path)
    return True


async def _serve(config: FleetConfig) -> None:
    ensure_secure_bind(config)
    lock = StateLock(config.state_path)
    lock.acquire()  # refuse a second instance sharing this state file
    registry = Registry(
        config.state_path,
        config.heartbeat_interval,
        config.ttl_factor,
        config.retention_days,
    )
    analytics, analytics_client = await build_analytics(config)
    app = build_fleet_app(config, registry, build_source(config), analytics)
    runner = await start_server(app, config.host, config.port)
    # Graceful shutdown: SIGTERM (e.g. `docker stop`) and SIGINT trip the stop
    # event so the app's cleanup runs (final state flush, source close).
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):  # not supported on Windows
            loop.add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        await runner.cleanup()
        if analytics_client is not None:
            await analytics_client.close()
        lock.release()


def _cmd_run() -> int:
    load_dotenv_if_available()
    config = FleetConfig.resolve()
    configure_logging(config.log_format)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_serve(config))
    return 0


def _cmd_init(args: argparse.Namespace, *, interactive: bool | None = None) -> int:
    if interactive is None:
        interactive = sys.stdin.isatty()

    def ask(label: str, current: str) -> str:
        if not interactive:
            return current
        reply = input(f"{label} [{current}]: ").strip()
        return reply or current

    token = args.token or wizard.generate_token()
    choices = wizard.InitChoices(
        token=token,
        host=ask("Bind host", args.host),
        port=int(ask("Port", str(args.port))),
        group=ask("Default fleet group", args.group),
        namespace=ask("Metric namespace", args.namespace),
        prometheus_url=ask("Prometheus URL (blank for push-only)", args.prometheus_url or "")
        or None,
        cors_origins=ask("CORS origins (blank for same-origin UI)", args.cors_origins or ""),
        public_url=ask("Public URL members reach", args.public_url),
    )
    paths = wizard.write_artifacts(choices, Path(args.out_dir))
    print(f"Wrote {paths['env']} and {paths['compose']}.")
    print("\nStart the control plane:\n  docker compose -f docker-compose.fleet.yml up -d")
    print("  # or: pip install 'argus-dpy[fleet]' && python -m argus.fleet")
    print(f"  # or (systemd): {wizard.systemd_hint(paths['env'])}")
    print("\nOpt each bot in:\n  " + wizard.member_snippet(choices).replace("\n", "\n  "))
    print(
        "\nOptional Prometheus auto-discovery (members set ARGUS_FLEET_SCRAPE_TARGET):\n"
        + wizard.prometheus_scrape_config(choices)
    )
    print("Keep .env secret; the token is shown there once.")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    report = asyncio.run(
        doctor.check(args.url, args.token, namespace=args.namespace, timeout=args.timeout)
    )
    for finding in report.findings:
        print(finding)
    return 0 if report.ok else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="argus-fleet", description="Argus Fleet control plane.")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("run", help="serve the control plane (default)")

    init_p = sub.add_parser("init", help="scaffold .env + compose + member snippet")
    init_p.add_argument("--out-dir", default=".")
    init_p.add_argument("--token", default=None, help="shared token (generated if omitted)")
    init_p.add_argument("--host", default="0.0.0.0")
    init_p.add_argument("--port", type=int, default=9190)
    init_p.add_argument("--group", default="default")
    init_p.add_argument("--namespace", default="discord")
    init_p.add_argument("--prometheus-url", dest="prometheus_url", default=None)
    init_p.add_argument("--cors-origins", dest="cors_origins", default=None)
    init_p.add_argument("--public-url", dest="public_url", default="http://fleet-host:9190")

    doctor_p = sub.add_parser("doctor", help="probe a running control plane")
    doctor_p.add_argument("--url", required=True, help="fleet base URL, e.g. http://host:9190")
    doctor_p.add_argument("--token", default=None)
    doctor_p.add_argument("--namespace", default=None, help="expected metric namespace")
    doctor_p.add_argument("--timeout", type=float, default=10.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cmd = args.cmd or "run"
    if cmd == "init":
        return _cmd_init(args)
    if cmd == "doctor":
        return _cmd_doctor(args)
    return _cmd_run()


if __name__ == "__main__":
    sys.exit(main())
