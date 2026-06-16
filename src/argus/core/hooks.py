"""Attach instrumentation to a discord.py bot, and detach it cleanly.

Listeners are additive (``bot.add_listener``), so Argus never clobbers the
user's own handlers. App command errors have no bot event, so the bot's
``CommandTree.on_error`` is chained (the original is preserved and still runs).
Rate-limit/log signal comes from a handler on the ``discord`` logger.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from argus.core.instrumentation import DiscordLogHandler, Instrumentation

_DISCORD_LOGGER = "discord"


@dataclass(slots=True)
class Registration:
    """Handle for undoing :func:`register` (used by the cog's teardown)."""

    bot: Any
    log_handler: logging.Handler
    listeners: list[tuple[str, Any]]
    tree: Any = None
    tree_original: Any = None
    _removed: bool = field(default=False)

    def remove(self) -> None:
        if self._removed:
            return
        self._removed = True
        logging.getLogger(_DISCORD_LOGGER).removeHandler(self.log_handler)
        for name, fn in self.listeners:
            try:
                self.bot.remove_listener(fn, name)
            except Exception:  # pragma: no cover - bot may already be torn down
                pass
        if self.tree is not None and self.tree_original is not None:
            self.tree.on_error = self.tree_original


def register(bot: Any, instrumentation: Instrumentation) -> Registration:
    """Register all listeners, chain the tree error handler, attach log handler."""
    listeners: list[tuple[str, Any]] = [
        ("on_interaction", instrumentation.on_interaction),
        ("on_app_command_completion", instrumentation.on_app_command_completion),
        ("on_command_completion", instrumentation.on_command_completion),
        ("on_command_error", instrumentation.on_command_error),
        ("on_socket_event_type", instrumentation.on_socket_event_type),
        ("on_shard_connect", instrumentation.on_shard_connect),
        ("on_shard_resumed", instrumentation.on_shard_resumed),
        ("on_shard_disconnect", instrumentation.on_shard_disconnect),
    ]
    for name, fn in listeners:
        bot.add_listener(fn, name)

    tree = getattr(bot, "tree", None)
    tree_original = None
    if tree is not None:
        tree_original = tree.on_error

        async def chained(
            interaction: Any, error: BaseException, _orig: Any = tree_original
        ) -> None:
            instrumentation.app_command_error(interaction, error)
            await _orig(interaction, error)

        tree.on_error = chained

    handler = DiscordLogHandler(instrumentation)
    logging.getLogger(_DISCORD_LOGGER).addHandler(handler)

    return Registration(
        bot=bot,
        log_handler=handler,
        listeners=listeners,
        tree=tree,
        tree_original=tree_original,
    )
