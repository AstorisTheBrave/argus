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

"""``argus-fleet doctor``: diagnose a running control plane (or reach it as a bot).

Connects to a fleet URL, checks ``/healthz`` reachability and the authenticated
``/api/fleet/view``, and reports cluster counts and any ``down`` clusters. Run it
from an operator box to inspect the fleet, or from a bot host to confirm the bot
can reach the control plane and the token works (the member reachability check).
Returns a structured report; the CLI prints it and exits non-zero on problems.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

import aiohttp


@dataclass(slots=True)
class DoctorReport:
    """The outcome of a doctor run: ok flag plus human-readable findings."""

    ok: bool = True
    findings: list[str] = field(default_factory=list)

    def add(self, ok: bool, message: str) -> None:
        self.findings.append(("[ok] " if ok else "[!!] ") + message)
        if not ok:
            self.ok = False


async def check(
    url: str,
    token: str | None = None,
    *,
    namespace: str | None = None,
    timeout: float = 10.0,
) -> DoctorReport:
    """Probe ``url``: reachability, auth, cluster health, and namespace match."""
    report = DoctorReport()
    base = url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    client_timeout = aiohttp.ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        try:
            async with session.get(f"{base}/healthz") as resp:
                report.add(resp.status == 200, f"GET /healthz -> {resp.status}")
        except (aiohttp.ClientError, TimeoutError) as exc:
            report.add(False, f"cannot reach {base}: {exc}")
            return report  # nothing else will work

        try:
            async with session.get(f"{base}/api/fleet/view", headers=headers) as resp:
                if resp.status == 401:
                    report.add(False, "GET /api/fleet/view -> 401 (missing or wrong token)")
                    return report
                report.add(resp.status == 200, f"GET /api/fleet/view -> {resp.status}")
                if resp.status == 200:
                    _inspect_view(await resp.json(), report)
        except (aiohttp.ClientError, TimeoutError) as exc:
            report.add(False, f"view request failed: {exc}")

        if namespace is not None:
            with contextlib.suppress(aiohttp.ClientError, TimeoutError):
                async with session.get(f"{base}/api/config", headers=headers) as resp:
                    if resp.status == 200:
                        actual = (await resp.json()).get("namespace")
                        report.add(
                            actual == namespace,
                            f"namespace {actual!r} (expected {namespace!r})",
                        )

    return report


def _inspect_view(view: dict[str, object], report: DoctorReport) -> None:
    fleets = view.get("fleets", [])
    if not isinstance(fleets, list):
        report.add(False, "view payload malformed (no fleets list)")
        return
    total = sum(int(f.get("clusters_total", 0)) for f in fleets)
    up = sum(int(f.get("clusters_up", 0)) for f in fleets)
    report.add(True, f"{len(fleets)} fleet(s), {up}/{total} clusters up")
    for f in fleets:
        down = int(f.get("clusters_total", 0)) - int(f.get("clusters_up", 0))
        if down:
            report.add(False, f"fleet {f.get('name')!r}: {down} cluster(s) down")
    if total == 0:
        report.add(True, "no clusters registered yet (members opt in via ARGUS_FLEET_URL)")
