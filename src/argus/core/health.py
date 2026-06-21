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

"""Live subsystem health for Argus itself, read at scrape time (invariant 4).

A single mutable :class:`HealthState` is created by the cog and closed over by
the ``argus_subsystem_up`` gauge callback. Because Argus is fail-open (a metrics
server that cannot bind must not crash the bot, invariant 5), an operator needs a
signal that distinguishes "the bot is fine but Argus degraded" from "everything
is healthy". This is that signal: each flag reflects whether one Argus subsystem
is currently working, and only configured subsystems are reported.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HealthState:
    """Mutable health flags for Argus' own subsystems.

    ``*_enabled`` gates whether a subsystem is reported at all (so a bot without
    the fleet client or the analytical sink does not emit a misleading ``0``).
    ``*_up`` is the live state, flipped by the cog as subsystems start and stop.
    """

    server_up: bool = False
    fleet_enabled: bool = False
    fleet_up: bool = False
    sink_enabled: bool = False
    sink_up: bool = True
    pushgateway_enabled: bool = False
    pushgateway_up: bool = False
