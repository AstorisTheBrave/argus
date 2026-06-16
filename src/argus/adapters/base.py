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
    def add_metric(self, metric: MetricDef) -> None: ...

    @abstractmethod
    def inc(
        self, name: str, labels: Mapping[str, str] | None = None, amount: float = 1.0
    ) -> None: ...

    @abstractmethod
    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None: ...

    @abstractmethod
    def set_info(self, name: str, info: Mapping[str, str]) -> None: ...
