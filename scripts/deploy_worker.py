"""Prepare and deploy only the audited Cloudflare Worker distribution."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "worker"
FORBIDDEN_DIRECTORIES = frozenset({".venv", ".venv-workers", ".git"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "prepare_worker.py")],
        cwd=ROOT,
        check=True,
    )
    _audit_distribution()

    npx = shutil.which("npx")
    if npx is None:
        raise SystemExit("npx was not found")
    command = [npx, "--yes", "wrangler", "deploy"]
    if args.dry_run:
        command.append("--dry-run")
    subprocess.run(command, cwd=DIST, check=True)
    return 0


def _audit_distribution() -> None:
    required = {
        DIST / "entry.py",
        DIST / "wrangler.toml",
        DIST / "translation_hub" / "app.py",
        DIST / "python_modules",
        DIST / "public",
    }
    missing = sorted(str(path.relative_to(ROOT)) for path in required if not path.exists())
    if missing:
        raise SystemExit(f"incomplete distribution: {', '.join(missing)}")

    forbidden = [
        path for path in DIST.rglob("*") if path.is_dir() and path.name in FORBIDDEN_DIRECTORIES
    ]
    if (DIST / "tests").exists():
        forbidden.append(DIST / "tests")
    if forbidden:
        names = ", ".join(str(path.relative_to(DIST)) for path in forbidden[:5])
        raise SystemExit(f"forbidden development directories in distribution: {names}")


if __name__ == "__main__":
    raise SystemExit(main())
