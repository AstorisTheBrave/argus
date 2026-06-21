"""Fallback launcher for bot panels that only run a single fixed entrypoint.

Some locked-down Docker hosts won't let you set a start command - they execute
one file and nothing else (this is the ``pane-start`` shim people end up writing
by hand). Point that entrypoint at this file and set ``BOT_FILE`` to your real
bot script. It loads a ``.env`` if present, then runs your bot.

You usually do NOT need this: Argus already auto-detects the host's
``SERVER_PORT``/``PORT`` and ``Argus(bot)`` loads ``.env`` when the
``argus-dpy[dotenv]`` extra is installed. Reach for this only when the start
command itself is not editable.

    BOT_FILE=bot.py python start_shim.py
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path


def _load_env(path: str = ".env") -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    if Path(path).is_file():
        load_dotenv(path, override=False)


def main() -> None:
    _load_env()
    target = os.environ.get("BOT_FILE", "bot.py")
    if not Path(target).is_file():
        raise SystemExit(f"start_shim: BOT_FILE {target!r} not found; set BOT_FILE to your bot")
    # Run the bot as if it were invoked directly (its __main__ block executes).
    runpy.run_path(target, run_name="__main__")


if __name__ == "__main__":
    main()
