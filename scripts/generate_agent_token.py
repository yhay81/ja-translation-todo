"""Generate an agent API token and the SHA-256 value stored by Cloudflare."""

from __future__ import annotations

import hashlib
import secrets


def main() -> int:
    token = "jat_" + secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    print("Keep agent_token secret; it is shown only in this terminal.")
    print(f"agent_token={token}")
    print(f"token_sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
