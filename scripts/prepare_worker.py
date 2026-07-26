"""Build a clean Cloudflare Worker directory without host virtual environments."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_ROOT = (ROOT / "dist").resolve()
DIST = (DIST_ROOT / "worker").resolve()
VENDOR = ROOT / "python_modules"


def ignored_vendor_files(_directory: str, names: list[str]) -> set[str]:
    ignored = {
        name
        for name in names
        if name == "__pycache__"
        or name.endswith((".pyc", ".pyo"))
        or name in {".synced", "pyvenv.cfg"}
    }
    return ignored


def main() -> int:
    if DIST.parent != DIST_ROOT or DIST_ROOT.parent != ROOT.resolve():
        raise RuntimeError(f"refusing to build outside the repository: {DIST}")
    if not VENDOR.is_dir() or not any(VENDOR.iterdir()):
        raise SystemExit(
            "python_modules is empty; run pywrangler sync (Linux/macOS) or the documented "
            "Pyodide-targeted uv install command (Windows)"
        )

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    for filename in ("entry.py", "wrangler.toml"):
        shutil.copy2(ROOT / filename, DIST / filename)
    shutil.copytree(ROOT / "public", DIST / "public")
    shutil.copytree(ROOT / "src" / "translation_hub", DIST / "translation_hub")
    shutil.copytree(
        VENDOR,
        DIST / "python_modules",
        ignore=ignored_vendor_files,
    )

    files = [path for path in DIST.rglob("*") if path.is_file()]
    size = sum(path.stat().st_size for path in files)
    print(f"prepared {DIST.relative_to(ROOT)}: {len(files)} files, {size / 1024 / 1024:.1f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
