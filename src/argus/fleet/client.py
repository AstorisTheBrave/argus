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

"""The member-side fleet client: opt-in, fail-open, bounded.

When ``fleet_url`` is set, ``ArgusCog.cog_load`` starts a ``FleetClient`` that
registers once (to claim its stable per-fleet number) then heartbeats every
``heartbeat_interval``, optionally attaching ``build_snapshot``. Every network
call is wrapped so a fleet outage or error never touches the bot loop (mirrors
invariant 5). At most one heartbeat is in flight; on failure it drops the sample
and retries on the next tick.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiohttp

if TYPE_CHECKING:
    from argus.config import ArgusConfig

log = logging.getLogger("argus")

SnapshotProvider = Callable[[], dict[str, Any]]

_IDENTITY_FILE = "argus-fleet-id"


class FleetClient:
    """Registers with and heartbeats to a fleet control plane, failing open."""

    __slots__ = ("_config", "_heartbeat_interval", "_identity", "_session", "_task")

    def __init__(self, config: ArgusConfig, heartbeat_interval: float = 15) -> None:
        self._config = config
        self._heartbeat_interval = heartbeat_interval
        self._identity = self._resolve_identity()
        self._session: aiohttp.ClientSession | None = None
        self._task: asyncio.Task[None] | None = None

    def _resolve_identity(self) -> str:
        """The stable identity: ``fleet_id``, else ``cluster_id``, else a UUID.

        Falling back to ``cluster_id`` means the fleet identity equals the
        Prometheus ``cluster`` label, so the push and Prometheus sources join the
        same way without extra configuration. Only when neither is set is a UUID
        generated and persisted to the state dir.
        """
        if self._config.fleet_id:
            return self._config.fleet_id
        if self._config.cluster_id:
            return self._config.cluster_id
        path = Path(self._config.fleet_state_dir) / _IDENTITY_FILE
        try:
            if path.exists():
                stored = path.read_text(encoding="utf-8").strip()
                if stored:
                    return stored
            identity = uuid.uuid4().hex
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(identity, encoding="utf-8")
            with contextlib.suppress(OSError):  # owner-only; do not let perms stop the bot
                path.chmod(0o600)
            return identity
        except OSError:
            # A read-only or missing state dir must not stop the bot; fall back
            # to an ephemeral identity (a new number on each restart).
            return uuid.uuid4().hex

    @property
    def identity(self) -> str:
        return self._identity

    def _headers(self) -> dict[str, str]:
        if self._config.fleet_token:
            return {"Authorization": f"Bearer {self._config.fleet_token}"}
        return {}

    async def start(self, snapshot_provider: SnapshotProvider | None = None) -> None:
        """Register, then run the heartbeat loop until :meth:`aclose`."""
        # Bound every call so a hung control plane cannot hold the single
        # in-flight heartbeat for aiohttp's 5-minute client default.
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        await self._register()
        self._task = asyncio.create_task(self._loop(snapshot_provider))

    async def _register(self) -> None:
        from argus import __version__

        if self._session is None:
            return
        try:
            body: dict[str, Any] = {
                "identity": self._identity,
                "fleet": self._config.fleet_group,
                "version": __version__,
            }
            if self._config.fleet_scrape_target:
                body["scrape_target"] = self._config.fleet_scrape_target
            async with self._session.post(
                f"{self._config.fleet_url}/fleet/register",
                json=body,
                headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
        except Exception as exc:  # fail open: never let fleet wiring touch the bot
            log.debug("argus fleet register failed (will retry via heartbeat): %s", exc)

    async def _loop(self, snapshot_provider: SnapshotProvider | None) -> None:
        while True:
            # Jitter (+/-10%) so a fleet restarting together does not heartbeat in
            # lockstep and thunder the control plane.
            jitter = self._heartbeat_interval * 0.1
            await asyncio.sleep(self._heartbeat_interval + random.uniform(-jitter, jitter))
            await self._heartbeat(snapshot_provider)

    async def _heartbeat(self, snapshot_provider: SnapshotProvider | None) -> None:
        if self._session is None:
            return
        try:
            body: dict[str, Any] = {"identity": self._identity}
            if snapshot_provider is not None:
                # A broken snapshot provider must not kill the loop either.
                body["snapshot"] = snapshot_provider()
            async with self._session.post(
                f"{self._config.fleet_url}/fleet/heartbeat",
                json=body,
                headers=self._headers(),
            ) as resp:
                if resp.status == 404:  # control plane forgot us; re-register
                    await self._register()
        except Exception as exc:  # fail open: drop this sample, never raise
            log.debug("argus fleet heartbeat failed (dropped): %s", exc)

    async def aclose(self) -> None:
        """Stop the loop and close the HTTP session."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._session is not None:
            await self._session.close()
            self._session = None
