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

"""Adapter ABC: the backend-side contract.

An adapter consumes the neutral registry (it satisfies the core
:class:`~argus.core.collector.MetricBackend` protocol) and renders it into a
concrete backend. Defined here so every adapter shares one shape.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from argus.core.collector import MetricDef


class Adapter(ABC):
    @abstractmethod
    def add_metric(self, metric: MetricDef) -> None:
        """Register a metric definition with the backend."""

    @abstractmethod
    def inc(self, name: str, labels: Mapping[str, str] | None = None, amount: float = 1.0) -> None:
        """Increment a counter."""

    @abstractmethod
    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        """Record a histogram observation."""

    @abstractmethod
    def set_info(self, name: str, info: Mapping[str, str]) -> None:
        """Set the static info labels."""
