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

"""Hatchling build hook: compile the SPA into the wheel.

At wheel-build time, if a ``frontend/`` source tree and npm are present, build
the SPA and copy it into ``src/argus/dashboard/static`` so the published wheel
ships prebuilt assets (end users need no Node). If npm is missing or the build
fails, the committed placeholder ``static/index.html`` is shipped instead.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        root = Path(self.root)
        frontend = root / "frontend"
        static = root / "src" / "argus" / "dashboard" / "static"
        if not frontend.is_dir():
            return

        npm = shutil.which("npm")
        if npm is None:
            print("argus: npm not found; shipping placeholder dashboard", file=sys.stderr)
            return

        try:
            subprocess.run([npm, "ci"], cwd=frontend, check=True)
            subprocess.run([npm, "run", "build"], cwd=frontend, check=True)
        except subprocess.CalledProcessError:
            print("argus: frontend build failed; shipping placeholder dashboard", file=sys.stderr)
            return

        dist = frontend / "dist"
        if dist.is_dir():
            if static.exists():
                shutil.rmtree(static)
            shutil.copytree(dist, static)
