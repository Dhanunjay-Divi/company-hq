#!/usr/bin/env python3
"""Build the public, source-only Company HQ archive deterministically."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile


APP_DIR = Path(__file__).resolve().parent
TOOLKIT_DIR = APP_DIR.parent
INTEGRATION_DIR = TOOLKIT_DIR / "clawteam" / "integration"
OUTPUT = APP_DIR / "SOURCE.zip"

APP_FILES = (
    "LICENSE",
    "README.md",
    "build-source.py",
    "index.html",
    "package-lock.json",
    "package.json",
    "postcss.config.cjs",
    "tailwind.config.cjs",
    "vite.config.ts",
)
APP_TREES = ("src", "vendor", "public")
INTEGRATION_FILES = (
    "CODEX-BRIDGE.md",
    "README.md",
    "codex_bridge.py",
    "provider_connections.py",
    "native_tools.py",
    "native_tasks.py",
    "access_settings.py",
    "test_native_tasks.py",
    "test_native_task_api.py",
    "test_access_settings.py",
    "folder_picker.py",
    "image_attachments.py",
    "test_provider_connections.py",
    "test_native_tools.py",
    "test_folder_picker.py",
    "test_image_attachments.py",
    "company_profile.py",
    "hq_api.py",
    "runtime_config.py",
    "secure_board.py",
    "test_codex_bridge.py",
    "test_runtime_config.py",
    "test_secure_board.py",
)
SCHEMA_DIR = "codex-app-server-schema-0.154.0-alpha.6.2"

FORBIDDEN_PARTS = {
    "__pycache__",
    "bindings",
    "conversations",
    "deps",
    "dist",
    "logs",
    "node_modules",
    "state",
}
FORBIDDEN_NAMES = {
    ".DS_Store",
    "SOURCE.zip",
    "saved-projects.json",
}
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _safe_files(root: Path, names: tuple[str, ...], trees: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for name in names:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"required regular file is missing: {path}")
        files.append(path)
    for tree_name in trees:
        tree = root / tree_name
        if not tree.is_dir() or tree.is_symlink():
            raise RuntimeError(f"required source directory is missing: {tree}")
        files.extend(path for path in tree.rglob("*") if path.is_file() and not path.is_symlink())
    return files


def _archive_entries() -> list[tuple[Path, PurePosixPath]]:
    entries: list[tuple[Path, PurePosixPath]] = []
    for path in _safe_files(APP_DIR, APP_FILES, APP_TREES):
        entries.append((path, PurePosixPath("company-hq") / path.relative_to(APP_DIR)))

    integration = _safe_files(
        INTEGRATION_DIR,
        INTEGRATION_FILES,
        (SCHEMA_DIR,),
    )
    for path in integration:
        entries.append(
            (
                path,
                PurePosixPath("clawteam/integration") / path.relative_to(INTEGRATION_DIR),
            )
        )

    for name in ("provider_registry.py", "discover.py", "routing.json", "THIRD_PARTY_NOTICES.md"):
        entries.append((TOOLKIT_DIR / name, PurePosixPath(name)))
    for path in _safe_files(TOOLKIT_DIR / "agency-agents", ("USE.md", "INSTALLATION.json", "REFERENCE-MANIFEST.json"), ("upstream",)):
        entries.append((path, PurePosixPath("agency-agents") / path.relative_to(TOOLKIT_DIR / "agency-agents")))

    entries.sort(key=lambda item: item[1].as_posix())
    archive_names: set[str] = set()
    for _, archive_path in entries:
        parts = set(archive_path.parts)
        if parts & FORBIDDEN_PARTS or archive_path.name in FORBIDDEN_NAMES:
            raise RuntimeError(f"forbidden archive path: {archive_path}")
        name = archive_path.as_posix()
        if name in archive_names:
            raise RuntimeError(f"duplicate archive path: {name}")
        archive_names.add(name)
    return entries


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.flag_bits = 0
    return info


def main() -> int:
    entries = _archive_entries()
    manifest_lines: list[str] = []
    payloads: list[tuple[str, bytes]] = []
    for source, archive_path in entries:
        data = source.read_bytes()
        name = archive_path.as_posix()
        payloads.append((name, data))
        manifest_lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}")

    manifest = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=APP_DIR, prefix=".SOURCE.", suffix=".zip", delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
            archive.writestr(_zip_info("SOURCE-MANIFEST.sha256"), manifest)
            for name, data in payloads:
                archive.writestr(_zip_info(name), data)
        os.chmod(temporary, 0o644)
        temporary.replace(OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)

    archive_digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(json.dumps({
        "archive": str(OUTPUT),
        "bytes": OUTPUT.stat().st_size,
        "files": len(payloads) + 1,
        "sha256": archive_digest,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
