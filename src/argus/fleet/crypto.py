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

"""Crypto for fleet lease secrets - standard primitives, no home-grown anything.

Lease secrets are 256-bit, CSPRNG-generated. They are verified by *hash*, never
stored in plaintext: a single fast keyed hash (HMAC-SHA256 with an optional
server-side pepper) is the correct choice for high-entropy secrets - bcrypt/argon2
are for low-entropy human passwords and would only add latency on the per-heartbeat
verify path. Comparison is constant-time. See the design spec and OWASP's secrets
guidance.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

# 32 bytes = 256 bits of entropy; brute-forcing the secret is infeasible, so no
# salt or slow KDF is needed (rainbow tables/collisions are not a concern here).
_SECRET_BYTES = 32


def generate_secret() -> str:
    """A new URL-safe, 256-bit lease secret."""
    return secrets.token_urlsafe(_SECRET_BYTES)


def hash_secret(secret: str, pepper: str | None = None) -> str:
    """HMAC-SHA256 hex digest of ``secret`` keyed by ``pepper`` (empty key if None).

    Only the digest is persisted. With a pepper (a separate server-side secret) a
    leaked state file alone cannot verify guesses - a distinct security boundary.
    """
    key = (pepper or "").encode("utf-8")
    return hmac.new(key, secret.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_secret(secret: str, stored_digest: str, pepper: str | None = None) -> bool:
    """Constant-time check that ``secret`` matches ``stored_digest``."""
    if not secret or not stored_digest:
        return False
    return hmac.compare_digest(hash_secret(secret, pepper), stored_digest)
