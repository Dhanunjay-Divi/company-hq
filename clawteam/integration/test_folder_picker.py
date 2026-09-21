from __future__ import annotations

import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

try:  # Supports both focused local and repository-root unittest invocation.
    from . import folder_picker
except ImportError:  # pragma: no cover - exercised by direct module invocation.
    import folder_picker


class FolderPickerTest(unittest.TestCase):
    def _temporary_directory(self):
        return tempfile.TemporaryDirectory(
            prefix="folder-picker-", dir=Path(__file__).resolve().parent
        )

    def _completed(self, stdout: str, returncode: int = 0):
        return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")

    def _choose(self, completed):
        with patch.object(folder_picker.platform, "system", return_value="Darwin"), patch.object(
            folder_picker.subprocess, "run", return_value=completed
        ) as run:
            choice = folder_picker.choose_folder()
        return choice, run

    def test_returns_canonical_directory_and_fixed_safe_argv(self):
        with tempfile.TemporaryDirectory(
            prefix="folder picker ", dir=Path(__file__).resolve().parent
        ) as temp:
            directory = Path(temp) / "selected folder"
            directory.mkdir()
            choice, run = self._choose(self._completed(f"{directory}\n"))

        self.assertEqual(choice, {"cancelled": False, "path": str(directory.resolve())})
        args, kwargs = run.call_args
        self.assertEqual(
            args[0],
            ["/usr/bin/osascript", "-e", folder_picker._CHOOSE_FOLDER_SCRIPT],
        )
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], folder_picker._PICKER_TIMEOUT_SECONDS)
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])

    def test_cancelled_picker_returns_successful_cancellation(self):
        choice, _ = self._choose(self._completed(f"{folder_picker._CANCELLED_SENTINEL}\n"))
        self.assertEqual(choice, {"cancelled": True, "path": None})

    def test_rejects_empty_relative_malformed_and_non_directory_paths(self):
        with self._temporary_directory() as temp:
            file_path = Path(temp) / "file"
            file_path.touch()
            cases = ("\n", "relative/path\n", "bad\x00path\n", f"{file_path}\n")
            for stdout in cases:
                with self.subTest(stdout=repr(stdout)):
                    with self.assertRaises(folder_picker.FolderPickerError):
                        self._choose(self._completed(stdout))

    def test_resolves_symlink_to_its_existing_directory(self):
        with self._temporary_directory() as temp:
            root = Path(temp)
            target = root / "target"
            link = root / "link"
            target.mkdir()
            link.symlink_to(target, target_is_directory=True)
            choice, _ = self._choose(self._completed(f"{link}\n"))
        self.assertEqual(choice, {"cancelled": False, "path": str(target.resolve())})

    def test_nonzero_exit_is_a_clear_error(self):
        with self.assertRaisesRegex(folder_picker.FolderPickerError, "exit code 2"):
            self._choose(self._completed("", returncode=2))

    def test_missing_path_is_a_clear_error(self):
        with self._temporary_directory() as temp:
            missing = Path(temp) / "missing"
            with self.assertRaisesRegex(folder_picker.FolderPickerError, "does not exist"):
                self._choose(self._completed(f"{missing}\n"))

    def test_timeout_is_a_clear_error(self):
        with patch.object(folder_picker.platform, "system", return_value="Darwin"), patch.object(
            folder_picker.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["/usr/bin/osascript"], 30),
        ):
            with self.assertRaisesRegex(folder_picker.FolderPickerError, "timed out"):
                folder_picker.choose_folder()

    def test_subprocess_start_failure_offers_manual_path_fallback(self):
        with patch.object(folder_picker.platform, "system", return_value="Darwin"), patch.object(
            folder_picker.subprocess, "run", side_effect=OSError("missing osascript")
        ):
            with self.assertRaisesRegex(
                folder_picker.FolderPickerUnavailableError, "manual path"
            ):
                folder_picker.choose_folder()

    def test_decoding_failure_is_a_clear_error(self):
        decoding_error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        with patch.object(folder_picker.platform, "system", return_value="Darwin"), patch.object(
            folder_picker.subprocess, "run", side_effect=decoding_error
        ):
            with self.assertRaisesRegex(folder_picker.FolderPickerError, "undecodable"):
                folder_picker.choose_folder()

    def test_requests_are_serialized_and_lock_releases_after_timeout(self):
        with self._temporary_directory() as temp:
            directory = Path(temp) / "selected"
            directory.mkdir()
            first_entered = threading.Event()
            permit_timeout = threading.Event()
            second_entered = threading.Event()
            call_count = 0
            count_lock = threading.Lock()
            results = []

            def fake_run(*_args, **_kwargs):
                nonlocal call_count
                with count_lock:
                    call_count += 1
                    call_number = call_count
                if call_number == 1:
                    first_entered.set()
                    self.assertTrue(permit_timeout.wait(1))
                    raise subprocess.TimeoutExpired(["/usr/bin/osascript"], 30)
                second_entered.set()
                return self._completed(f"{directory}\n")

            def request():
                try:
                    results.append(folder_picker.choose_folder())
                except Exception as exc:  # Capture the first request's expected timeout.
                    results.append(exc)

            with patch.object(folder_picker.platform, "system", return_value="Darwin"), patch.object(
                folder_picker.subprocess, "run", side_effect=fake_run
            ):
                first = threading.Thread(target=request)
                second = threading.Thread(target=request)
                first.start()
                self.assertTrue(first_entered.wait(1))
                second.start()
                self.assertFalse(second_entered.wait(0.1))
                permit_timeout.set()
                first.join(1)
                second.join(1)

            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(call_count, 2)
            self.assertTrue(second_entered.is_set())
            self.assertTrue(any(isinstance(result, folder_picker.FolderPickerError) for result in results))
            self.assertIn({"cancelled": False, "path": str(directory.resolve())}, results)

    def test_unsupported_system_offers_manual_path_fallback(self):
        with patch.object(folder_picker.platform, "system", return_value="Linux"), patch.object(
            folder_picker.subprocess, "run"
        ) as run:
            with self.assertRaisesRegex(
                folder_picker.FolderPickerUnavailableError, "manual path"
            ):
                folder_picker.choose_folder()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
