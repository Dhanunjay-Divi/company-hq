import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_updates as checker


class UpdateTests(unittest.TestCase):
    def test_metadata_not_executed(self):
        def fake(endpoint):
            return ([{"sha": "a" * 40}], None) if "commits?" in endpoint else ({"tag_name": "$(not-executed)"}, None)
        row = checker.check_repo({"repo": "owner/repo", "reviewed_ref": "b" * 40}, fake)
        self.assertTrue(row["source_changed_since_review"])
        self.assertEqual(row["latest_release"], "$(not-executed)")

    def test_missing_release_is_not_a_failure(self):
        def fake(endpoint):
            return ([{"sha": "a" * 40}], None) if "commits?" in endpoint else (None, "http-404")
        row = checker.check_repo({"repo": "owner/repo"}, fake)
        self.assertIsNone(row["latest_release"])
        self.assertNotIn("release_error", row)

    def test_errors_are_not_claimed_current(self):
        row = checker.check_repo({"repo": "owner/repo"}, lambda _: (None, "http-403"))
        self.assertEqual(row["head_error"], "http-403")
        self.assertNotIn("head", row)

    def test_rejects_arbitrary_endpoints(self):
        with self.assertRaises(ValueError):
            checker.check_repo({"repo": "../private/path"}, lambda _: self.fail("network must not run"))

    def test_cache_and_private_atomic_write(self):
        now = dt.datetime.now(dt.timezone.utc)
        catalog = [{"repo": "owner/repo"}]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(checker, "BASE", Path(directory)), patch.object(checker, "CACHE", Path(directory) / "cache.json"):
                payload = {"schema": 1, "checked_unix": now.timestamp(), "catalog_repositories": ["owner/repo"],
                           "catalog_fingerprint": checker.catalog_fingerprint(catalog)}
                checker.save(payload)
                self.assertEqual(checker.cached(catalog, now), payload)
                self.assertEqual(checker.CACHE.stat().st_mode & 0o777, 0o600)
                self.assertIsNone(checker.cached(catalog, now + dt.timedelta(days=2)))
                self.assertIsNone(checker.cached(catalog, now - dt.timedelta(days=1)))
                self.assertIsNone(checker.cached([{"repo": "different/repo"}], now))
                self.assertIsNone(checker.cached([{"repo": "owner/repo", "reviewed_ref": "a" * 40}], now))
                self.assertIsNone(checker.cached([{"repo": "owner/repo", "version": "next"}], now))


if __name__ == "__main__":
    unittest.main()
