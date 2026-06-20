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

"""Argus Fleet: an opt-in, standalone control plane.

A separate service (its own process and container, never inside a bot) that
gives operators a readable, multi-tier view of many Argus-instrumented bot
processes ("clusters"), grouped by region/fleet. Bots stay light; the heavy
aggregation and UI run on their own host. Importing this package has no effect
on a bot unless ``ARGUS_FLEET_URL`` is set (see :class:`argus.config.ArgusConfig`).
"""

from __future__ import annotations

from argus.fleet.config import FleetConfig

__all__ = ["FleetConfig"]
