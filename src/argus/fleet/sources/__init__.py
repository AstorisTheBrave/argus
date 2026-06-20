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

"""Fleet data sources: push (self-contained) and Prometheus, behind one ABC."""

from __future__ import annotations

from argus.fleet.sources.base import ClusterValues, FleetDataSource, assemble
from argus.fleet.sources.composite import CompositeSource
from argus.fleet.sources.push import PushSource

__all__ = ["ClusterValues", "CompositeSource", "FleetDataSource", "PushSource", "assemble"]
