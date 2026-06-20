"""JSON metric snapshot (plan task 2.1)."""

from __future__ import annotations

from typing import Any

from argus.adapters.prometheus import PrometheusAdapter
from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.metrics import define_metrics
from argus.dashboard.snapshot import build_snapshot
from tests.conftest import FakeBot


def _snapshot() -> dict[str, Any]:
    bot = FakeBot()
    registry = MetricRegistry()
    names = define_metrics(registry, bot, ArgusConfig.resolve(environ={}))
    adapter = PrometheusAdapter()
    registry.attach(adapter)
    registry.set_info(names.bot_info, {"discord_py_version": "2.7.1", "argus_version": "0.1.0"})
    registry.inc(
        names.interactions_total,
        {"type": "application_command", "status": "received", "cluster": "default"},
    )
    registry.observe(
        names.app_command_duration_seconds, 0.2, {"command": "ping", "cluster": "default"}
    )
    return build_snapshot(adapter.registry)


def test_snapshot_includes_live_gauges() -> None:
    snap = _snapshot()["metrics"]
    guilds = snap["discord_guilds"]
    assert guilds["type"] == "gauge"
    sample = guilds["samples"][0]
    assert sample["labels"] == {"cluster": "default"}
    assert sample["value"] == 3.0


def test_snapshot_includes_counter_and_histogram_buckets() -> None:
    snap = _snapshot()["metrics"]
    # prometheus_client strips the _total suffix from the counter *family* name
    # (individual samples keep discord_interactions_total).
    counter = snap["discord_interactions"]
    assert counter["type"] == "counter"
    assert any(s["name"] == "discord_interactions_total" for s in counter["samples"])
    hist = snap["discord_app_command_duration_seconds"]
    assert hist["type"] == "histogram"
    assert any(s["name"].endswith("_bucket") for s in hist["samples"])


def test_snapshot_has_no_forbidden_labels() -> None:
    snap = _snapshot()["metrics"]
    for family in snap.values():
        for sample in family["samples"]:
            for forbidden in ("guild_id", "user_id", "channel_id"):
                assert forbidden not in sample["labels"]
