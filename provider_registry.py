"""Bounded local provider installation inventory; never probes accounts or runtimes."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import plistlib
import shutil


_PROVIDERS = (
    ("codex", "Codex", ("codex",), "ChatGPT.app", "com.openai.chat"),
    ("claude", "Claude", ("claude",), "Claude.app", "com.anthropic.claudefordesktop"),
    ("kimi", "Kimi Code", ("kimi",), "Kimi Code.app", "com.kimi.code.desktop"),
    ("zai", "Z Code", ("zai", "glm"), "ZCode.app", "dev.zcode.app"),
    ("cursor", "Cursor", ("cursor-agent",), "Cursor.app", None),
    ("grok", "Grok Bot", ("grok",), "Grok Bot.app", "com.anysphere.sand"),
    ("ollama", "Ollama", ("ollama",), "Ollama.app", None),
)
_CODEX_RESOURCE_CLI = Path("/Applications/ChatGPT.app/Contents/Resources/codex")


def _executable(path: str | Path | None) -> str | None:
    if not path:
        return None
    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        return None
    parts = resolved.parts
    if ".app" in "".join(parts).lower() and "Contents" in parts and "MacOS" in parts:
        return None
    return str(resolved) if resolved.is_file() and os.access(resolved, os.X_OK) else None


def _cli_directories(home: Path) -> tuple[Path, ...]:
    return (
        home / ".local" / "bin", home / ".cargo" / "bin", home / "bin",
        Path("/opt/homebrew/bin"), Path("/usr/local/bin"),
    )


def _cli_path(provider_id: str, names: tuple[str, ...], environment: dict[str, str], home: Path, which) -> str | None:
    override = _executable(environment.get(f"COMPANY_HQ_{provider_id.upper()}_PATH"))
    if override:
        return override
    for name in names:
        found = _executable(which(name))
        if found:
            return found
    for directory in _cli_directories(home):
        for name in names:
            found = _executable(directory / name)
            if found:
                return found
    special = {
        "claude": (home / ".claude" / "local" / "claude",),
        "kimi": (home / ".local" / "share" / "uv" / "tools" / "kimi-cli" / "bin" / "kimi",),
        "codex": (_CODEX_RESOURCE_CLI,),
    }
    for candidate in special.get(provider_id, ()):
        found = _executable(candidate)
        if found:
            return found
    return None


def _desktop_app(roots: tuple[Path, ...], name: str, bundle_id: str | None) -> str | None:
    for root in roots:
        app = root / name
        if not app.is_dir():
            continue
        if bundle_id:
            try:
                with (app / "Contents" / "Info.plist").open("rb") as source:
                    if plistlib.load(source).get("CFBundleIdentifier") != bundle_id:
                        continue
            except (OSError, plistlib.InvalidFileException):
                continue
        return str(app)
    return None


def inventory(*, environ: dict[str, str] | None = None, app_roots: tuple[Path, ...] | None = None,
              which=shutil.which, now: dt.datetime | None = None, home: Path | None = None) -> dict:
    """Return local presence only; authentication and provider execution remain untouched."""
    environment = os.environ if environ is None else environ
    user_home = Path.home() if home is None else home
    roots = (
        Path("/Applications"), user_home / "Applications",
        user_home / "Applications" / "Chrome Apps.localized", Path("/Applications/Chrome Apps.localized"),
    ) if app_roots is None else app_roots
    providers = []
    for provider_id, label, names, app_name, bundle_id in _PROVIDERS:
        cli_path = _cli_path(provider_id, names, environment, user_home, which)
        desktop_path = _desktop_app(roots, app_name, bundle_id)
        providers.append({
            "id": provider_id,
            "label": label,
            "cliPath": cli_path,
            "desktopPath": desktop_path,
            "installed": bool(cli_path or desktop_path),
            "authentication": "not_checked",
            "runtimeReady": provider_id == "codex" and bool(cli_path),
            "reason": (
                "Native Codex CLI detected; account state is not checked."
                if provider_id == "codex" and cli_path
                else "Desktop app detected; no Company HQ runtime adapter is enabled."
                if desktop_path and not cli_path
                else "CLI detected; no Company HQ runtime adapter is enabled."
                if cli_path
                else "No supported local CLI or desktop app was detected."
            ),
        })
    timestamp = now or dt.datetime.now(dt.timezone.utc)
    return {"checkedAt": timestamp.astimezone(dt.timezone.utc).isoformat(), "providers": providers}
