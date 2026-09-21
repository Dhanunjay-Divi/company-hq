"""Small, local-only native folder selection adapter."""

from __future__ import annotations

from pathlib import Path
import platform
import subprocess
import threading
from typing import TypedDict


_PICKER_TIMEOUT_SECONDS = 30
_CANCELLED_SENTINEL = "__COMPANY_HQ_FOLDER_PICKER_CANCELLED__"
_CHOOSE_FOLDER_SCRIPT = f'''try
    return POSIX path of (choose folder)
on error number -128
    return "{_CANCELLED_SENTINEL}"
end try'''
_picker_lock = threading.Lock()


class FolderChoice(TypedDict):
    cancelled: bool
    path: str | None


class FolderPickerError(RuntimeError):
    """The native picker could not return a valid directory."""


class FolderPickerUnavailableError(FolderPickerError):
    """The caller should offer its manual-path fallback."""


def _remove_transport_newline(value: str) -> str:
    """Remove only osascript's final line terminator, preserving path spaces."""
    if value.endswith("\r\n"):
        return value[:-2]
    if value.endswith("\n") or value.endswith("\r"):
        return value[:-1]
    return value


def _canonical_directory(value: str) -> str:
    if not value:
        raise FolderPickerError("Native folder picker returned an empty path.")
    if "\x00" in value:
        raise FolderPickerError("Native folder picker returned an invalid path.")

    candidate = Path(value)
    if not candidate.is_absolute():
        raise FolderPickerError("Native folder picker returned a non-absolute path.")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise FolderPickerError("Selected folder does not exist.") from exc
    try:
        is_directory = resolved.is_dir()
    except OSError as exc:
        raise FolderPickerError("Selected folder cannot be accessed.") from exc
    if not is_directory:
        raise FolderPickerError("Selected path is not a directory.")
    return str(resolved)


def choose_folder() -> FolderChoice:
    """Show macOS's native folder chooser and return a canonical directory path.

    Unsupported systems raise ``FolderPickerUnavailableError`` so callers can
    offer a manual-path fallback.  The lock prevents multiple native dialogs
    from racing each other in a single process.
    """
    if platform.system() != "Darwin":
        raise FolderPickerUnavailableError(
            "Native folder picker is unavailable on this operating system; use a manual path."
        )

    with _picker_lock:
        try:
            result = subprocess.run(
                ["/usr/bin/osascript", "-e", _CHOOSE_FOLDER_SCRIPT],
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=_PICKER_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise FolderPickerError("Native folder picker timed out.") from exc
        except UnicodeError as exc:
            raise FolderPickerError("Native folder picker returned undecodable output.") from exc
        except OSError as exc:
            raise FolderPickerUnavailableError(
                "Native folder picker could not be started; use a manual path."
            ) from exc

    if result.returncode != 0:
        raise FolderPickerError(
            f"Native folder picker failed with exit code {result.returncode}."
        )
    if not isinstance(result.stdout, str):
        raise FolderPickerError("Native folder picker returned invalid output.")

    selected = _remove_transport_newline(result.stdout)
    if selected == _CANCELLED_SENTINEL:
        return {"cancelled": True, "path": None}
    return {"cancelled": False, "path": _canonical_directory(selected)}
