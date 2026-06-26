"""Validate the shipped operational assets: Grafana dashboards and the rules file.

These are config, not Python, but a broken dashboard or a missing rules file
should fail the build, not surprise an operator. The PromQL semantics are
verified separately by promtool in CI; here we check structure and wiring.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DASHBOARDS = sorted((_ROOT / "grafana" / "dashboards").glob("*.json"))
_DATASOURCE_UID = "argus-prometheus"


def test_dashboards_present() -> None:
    names = {p.stem for p in _DASHBOARDS}
    assert {"overview", "interactions", "gateway", "health"} <= names


@pytest.mark.parametrize("path", _DASHBOARDS, ids=lambda p: p.stem)
def test_dashboard_is_well_formed(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["uid"]
    assert data["title"]
    assert data["schemaVersion"]
    panels = data["panels"]
    assert panels, "dashboard has no panels"
    for panel in panels:
        assert "title" in panel and "type" in panel
        for target in panel.get("targets", []):
            # Every query must resolve against the provisioned datasource.
            assert target["datasource"]["uid"] == _DATASOURCE_UID
            assert target.get("expr"), f"empty expr in {path.stem}/{panel['title']}"


def test_rules_files_present() -> None:
    rules = _ROOT / "prometheus" / "rules" / "argus.rules.yml"
    tests = _ROOT / "prometheus" / "rules" / "argus.rules.test.yml"
    assert rules.is_file()
    assert tests.is_file()
    # The recording rules must not reappear with the clamp_min denominator bug
    # (ignore comment lines, which legitimately mention it).
    expr_lines = "\n".join(
        line
        for line in rules.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "clamp_min" not in expr_lines


def test_compose_grafana_has_no_default_password_and_allows_embedding() -> None:
    compose = (_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    # The Grafana admin password must come from the environment with no shipped
    # default (compose fails fast if unset) -- never a hardcoded "admin".
    assert "GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD" in compose
    assert "GF_SECURITY_ADMIN_PASSWORD: admin" not in compose
    # Embedding must be enabled so the dashboard's Grafana tab can frame the boards.
    assert "GF_SECURITY_ALLOW_EMBEDDING" in compose
