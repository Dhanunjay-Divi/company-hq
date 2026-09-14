#!/usr/bin/env python3
"""Read public GitHub metadata for the fixed toolkit catalog; never install code."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.request

BASE = Path(__file__).resolve().parent
CACHE = BASE / "upstream-status.json"
MAX_AGE = 24 * 60 * 60


def catalog_fingerprint(catalog):
    return hashlib.sha256(json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def api_get(endpoint):
    req = urllib.request.Request(
        "https://api.github.com/" + endpoint,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "local-agent-toolkit-update-check/1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            return None, "response-too-large"
        return json.loads(raw), None
    except urllib.error.HTTPError as exc:
        return None, "http-" + str(exc.code)
    except (OSError, ValueError):
        return None, "network-or-json-error"


def check_repo(item, fetch=api_get):
    repo = item["repo"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid catalog repository")
    result = {"repo": repo, "reviewed_ref": item.get("reviewed_ref"), "reviewed_version": item.get("version")}
    commits, err = fetch("repos/" + repo + "/commits?per_page=1")
    head = commits[0].get("sha") if isinstance(commits, list) and commits and isinstance(commits[0], dict) else None
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        result["head_error"] = err or "invalid-commit-response"
    else:
        result["head"] = head
        result["source_changed_since_review"] = head != item.get("reviewed_ref") if item.get("reviewed_ref") else None
    release, err = fetch("repos/" + repo + "/releases/latest")
    if isinstance(release, dict) and isinstance(release.get("tag_name"), str):
        # Metadata is untrusted data, never instructions or shell arguments.
        result["latest_release"] = release["tag_name"][:128]
        result["release_published_at"] = release.get("published_at")
    elif err == "http-404":
        result["latest_release"] = None
    else:
        result["release_error"] = err or "invalid-release-response"
    return result


def cached(catalog, now):
    try:
        payload = json.loads(CACHE.read_text())
        age = now.timestamp() - payload["checked_unix"]
        expected = [r["repo"] for r in catalog]
        if (0 <= age < MAX_AGE and payload["catalog_repositories"] == expected
                and payload["schema"] == 1 and payload["catalog_fingerprint"] == catalog_fingerprint(catalog)):
            return payload
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def save(payload):
    fd, temporary = tempfile.mkstemp(prefix=".upstream-", suffix=".json", dir=BASE)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(payload, out, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, CACHE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Ignore the 24-hour cache; no installations")
    args = parser.parse_args()
    catalog = json.loads((BASE / "catalog.json").read_text())["repositories"]
    now = dt.datetime.now(dt.timezone.utc)
    result = None if args.refresh else cached(catalog, now)
    used_cache = result is not None
    if result is None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(check_repo, catalog))
        result = {
            "schema": 1, "checked_at": now.isoformat(), "checked_unix": now.timestamp(),
            "catalog_repositories": [r["repo"] for r in catalog], "repositories": rows,
            "catalog_fingerprint": catalog_fingerprint(catalog),
            "mutations": "Only this local metadata cache; no installation, account, project, or deployment changes",
        }
        save(result)
    print(json.dumps({"cached": used_cache, **result}, indent=2))
    return 1 if any("head_error" in row or "release_error" in row for row in result["repositories"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
