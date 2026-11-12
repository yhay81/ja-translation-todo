"""Build a clean Cloudflare Worker directory without host virtual environments."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_ROOT = (ROOT / "dist").resolve()
DIST = (DIST_ROOT / "worker").resolve()
VENDOR = ROOT / "python_modules"


def ignored_python_files(directory: str, names: list[str]) -> set[str]:
    ignored = {
        name
        for name in names
        if name == "__pycache__"
        or name.endswith((".pyc", ".pyo"))
        or name in {".synced", "pyvenv.cfg"}
    }
    if Path(directory) == VENDOR:
        # uv generates host-specific console scripts alongside the target packages.
        ignored.update({"bin", "Scripts", ".lock"})
    return ignored


def main() -> int:
    if DIST.parent != DIST_ROOT or DIST_ROOT.parent != ROOT.resolve():
        raise RuntimeError(f"refusing to build outside the repository: {DIST}")
    if not VENDOR.is_dir() or not any(VENDOR.iterdir()):
        raise SystemExit(
            "python_modules is empty; sync the Pyodide dependencies from pylock.toml "
            "as described in README.md"
        )

    DIST.mkdir(parents=True, exist_ok=True)
    # Wrangler keeps the local D1 database under .wrangler/state between builds.
    for path in DIST.iterdir():
        if path.name == ".wrangler":
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()

    for filename in ("entry.py", "wrangler.toml"):
        shutil.copy2(ROOT / filename, DIST / filename)
    shutil.copytree(ROOT / "public", DIST / "public")
    shutil.copytree(
        ROOT / "src" / "translation_hub", DIST / "translation_hub", ignore=ignored_python_files
    )
    shutil.copytree(
        VENDOR,
        DIST / "python_modules",
        ignore=ignored_python_files,
    )

    files = []
    for root, directories, names in DIST.walk():
        if root == DIST and ".wrangler" in directories:
            directories.remove(".wrangler")
        files.extend(root / name for name in names)
    size = sum(path.stat().st_size for path in files)
    print(f"prepared {DIST.relative_to(ROOT)}: {len(files)} files, {size / 1024 / 1024:.1f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
