"""End-to-end: a real `python -m argus.fleet` process + an HTTP member round-trip.

Spawns the actual entrypoint as a subprocess (loopback bind, no token needed) and
drives it over HTTP, exercising the full server stack as deployed - not the
in-process aiohttp test client.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _post(url: str, payload: dict[str, object]) -> tuple[int, bytes]:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _wait_healthy(base: str, proc: subprocess.Popen[bytes], timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f"control plane exited early (code {proc.returncode})")
        try:
            status, _ = _get(f"{base}/healthz")
            if status == 200:
                return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.2)
    raise AssertionError("control plane did not become healthy in time")


def test_member_round_trip_against_real_process(tmp_path: Path) -> None:
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        {
            "ARGUS_FLEET_HOST": "127.0.0.1",  # loopback: starts without a token
            "ARGUS_FLEET_PORT": str(port),
            "ARGUS_FLEET_STATE": str(tmp_path / "state.json"),
            "ARGUS_FLEET_HEARTBEAT_INTERVAL": "1",
        }
    )
    proc = subprocess.Popen([sys.executable, "-m", "argus.fleet"], env=env)
    try:
        _wait_healthy(base, proc)

        status, body = _post(f"{base}/fleet/register", {"identity": "asia-0", "fleet": "asia"})
        assert status == 200
        assert json.loads(body)["number"] == 1

        snapshot = {
            "metrics": {
                "discord_guilds": {
                    "samples": [{"name": "discord_guilds", "labels": {}, "value": 9}]
                }
            }
        }
        status, _ = _post(f"{base}/fleet/heartbeat", {"identity": "asia-0", "snapshot": snapshot})
        assert status == 204

        status, body = _get(f"{base}/api/fleet/view")
        assert status == 200
        view = json.loads(body)
        asia = next(f for f in view["fleets"] if f["name"] == "asia")
        assert asia["clusters_total"] == 1
        assert asia["clusters"][0]["metrics"]["guilds"] == 9
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
