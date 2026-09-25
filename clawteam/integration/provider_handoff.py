"""Fail-closed, same-team provider handoff journal.

This helper deliberately does not transfer conversation context, retry a turn, or
start a replacement after recovery.  ProviderHub owns the synchronized binding
rotation because only it can stop its runtime and join its watcher safely.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from typing import Any, Callable


class HandoffError(RuntimeError):
    pass


_TERMINAL_STATES = {"idle", "error"}
_TERMINAL_CHILD_STATES = {"completed", "stopped", "error", "idle", "offline", "failed"}


class ProviderHandoff:
    """Create a manual-recovery journal around a verified idle provider swap."""

    def __init__(self, state_dir: str | Path, *, now: Callable[[], float] = time.time) -> None:
        self.directory = Path(state_dir).expanduser().resolve() / "provider-handoffs"
        self._now = now

    @staticmethod
    def _team_key(team: str) -> str:
        if not isinstance(team, str) or not team.strip() or len(team) > 200:
            raise HandoffError("team must be a non-empty short string")
        return hashlib.sha256(team.encode("utf-8")).hexdigest()

    def _path(self, team: str) -> Path:
        return self.directory / f"{self._team_key(team)}.json"

    def _archive_path(self, team: str, handoff_id: str) -> Path:
        return self.directory / "archive" / f"{self._team_key(team)}.{handoff_id}.json"

    def _read(self, team: str) -> dict[str, Any] | None:
        path = self._path(team)
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65_536:
            raise HandoffError("handoff journal must be a small regular file")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HandoffError("handoff journal is unreadable") from exc
        if not isinstance(value, dict) or value.get("version") != 1 or value.get("teamKey") != self._team_key(team):
            raise HandoffError("handoff journal does not belong to this team")
        return value

    def _save(self, team: str, journal: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self._path(team)
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(json.dumps(journal, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, path)

    def _archive_started(self, team: str, journal: dict[str, Any]) -> None:
        """Retain a completed audit record without blocking a later handoff."""
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = self._archive_path(team, journal["id"])
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if destination.exists():
            raise HandoffError("completed handoff archive already exists")
        os.replace(self._path(team), destination)

    def _event(self, journal: dict[str, Any], kind: str, **details: Any) -> None:
        # These are routing facts only.  Prompts, transcripts, provider auth, and
        # raw provider errors never enter the durable handoff record.
        journal.setdefault("timeline", []).append({"at": self._now(), "kind": kind, **details})

    @staticmethod
    def _native_quota_provenance(value: Any, provider: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise HandoffError("native quota exhaustion provenance is required")
        required = value.get("source") == "native-provider" and value.get("kind") == "quota_exhausted"
        account = value.get("accountId")
        if not required or value.get("provider") != provider or not isinstance(account, str) or not account:
            raise HandoffError("quota provenance must be a matching native provider account exhaustion")
        reset = value.get("resetAt")
        if reset is not None and (isinstance(reset, bool) or not isinstance(reset, (int, float))):
            raise HandoffError("quota provenance resetAt must be an epoch or null")
        return {"provider": provider, "accountId": account, "resetAt": reset}

    @staticmethod
    def _candidate(policy: Any, catalog: list[dict[str, Any]]) -> dict[str, Any]:
        decision = policy.decide(catalog, role="supervisor")
        candidate = decision.get("candidate") if isinstance(decision, dict) else None
        if not isinstance(candidate, dict) or not isinstance(candidate.get("provider"), str) or not isinstance(candidate.get("model"), str):
            raise HandoffError("no safe policy-approved handoff candidate is available")
        return candidate

    def plan(self, hub: Any, policy: Any, team: str, catalog: list[dict[str, Any],], quota_provenance: dict[str, Any]) -> dict[str, Any]:
        """Journal a policy-approved fallback after structured native quota evidence."""
        existing = self._read(team)
        if existing:
            if existing.get("phase") == "started":
                self._archive_started(team, existing)
            elif existing.get("phase") in {"planned", "checkpointed"}:
                return self.describe(team)
            else:
                raise HandoffError("an incomplete handoff journal requires explicit operator recovery")
        status = hub.status(team)
        if not isinstance(status, dict) or not isinstance(status.get("provider"), str) or not isinstance(status.get("model"), str):
            raise HandoffError("current provider binding is unavailable")
        provenance = self._native_quota_provenance(quota_provenance, status["provider"])
        # Record the native provider fact first so candidate selection cannot
        # select another model on the exhausted account.
        policy.record_quota_exhausted(provenance["provider"], provenance["accountId"], provenance["resetAt"])
        candidate = self._candidate(policy, catalog)
        if candidate.get("provider") == provenance["provider"] and candidate.get("accountId") == provenance["accountId"]:
            raise HandoffError("policy candidate remains on the exhausted provider account")
        journal = {
            "version": 1,
            "id": uuid.uuid4().hex,
            "teamKey": self._team_key(team),
            "phase": "planned",
            "from": {"provider": status["provider"], "model": status["model"], "sessionId": status.get("sessionId")},
            "to": {"provider": candidate["provider"], "model": candidate["model"], "accountId": candidate.get("accountId")},
            "tokenEpochs": [{"provider": status["provider"], "model": status["model"], "reportedTokens": (status.get("usageSummary") or {}).get("reportedTokens")}],
            "timeline": [],
        }
        self._event(journal, "planned", oldSeq=status.get("lastEventSeq"), quotaResetAt=provenance["resetAt"])
        self._save(team, journal)
        return self.describe(team)

    @staticmethod
    def _checkpoint_reason(status: Any) -> str | None:
        if not isinstance(status, dict) or status.get("state") not in _TERMINAL_STATES:
            return "runtime must be terminal idle or error"
        native = status.get("nativeStatus")
        if not isinstance(native, dict):
            return "native runtime checkpoint is unavailable"
        if native.get("currentTurnId") is not None or native.get("activeTurnId") is not None:
            return "native runtime still has an active turn"
        if "activeToolCalls" in native and native.get("activeToolCalls"):
            return "native runtime still has active tool calls"
        inventory = native.get("childInventory")
        if not isinstance(inventory, dict) or inventory.get("complete") is not True:
            return "native child inventory is not verified complete"
        if status.get("pendingApprovals"):
            return "pending approvals must be resolved or rejected"
        if status.get("unrecoverableRequests"):
            return "unresolved native requests prevent handoff"
        children = status.get("children")
        if not isinstance(children, list):
            return "child runtime state is unavailable"
        for child in children:
            if not isinstance(child, dict) or child.get("verified") is not True or child.get("state") not in _TERMINAL_CHILD_STATES:
                return "active or unverified child work prevents handoff"
        return None

    @staticmethod
    def _source_matches(journal: dict[str, Any], status: Any) -> bool:
        if not isinstance(status, dict):
            return False
        source = journal.get("from")
        return isinstance(source, dict) and all(
            status.get(key) == source.get(key)
            for key in ("provider", "model", "sessionId")
        )

    def checkpoint(self, hub: Any, team: str, handoff_id: str) -> dict[str, Any]:
        journal = self._read(team)
        if not journal or journal.get("id") != handoff_id or journal.get("phase") not in {"planned", "checkpointed"}:
            raise HandoffError("handoff is not available for checkpointing")
        status = hub.status(team)
        reason = None if self._source_matches(journal, status) else "current provider binding no longer matches the planned handoff"
        reason = reason or self._checkpoint_reason(status)
        if reason:
            self._event(journal, "checkpoint-blocked", reason=reason)
            self._save(team, journal)
            return {"ready": False, "reason": "requires stopped checkpoint: " + reason, "handoff": self.describe(team)}
        journal["phase"] = "checkpointed"
        journal["checkpoint"] = {"oldSeq": status.get("lastEventSeq"), "sessionId": status.get("sessionId")}
        self._event(journal, "checkpointed", oldSeq=status.get("lastEventSeq"))
        self._save(team, journal)
        return {"ready": True, "handoff": self.describe(team)}

    def execute(self, hub: Any, team: str, handoff_id: str, resume_prompt: str) -> dict[str, Any]:
        """Rotate a fully stopped binding, then begin one caller-supplied new turn."""
        if not isinstance(resume_prompt, str) or not resume_prompt.strip():
            raise HandoffError("a new, caller-supplied resume prompt is required")
        journal = self._read(team)
        if not journal or journal.get("id") != handoff_id or journal.get("phase") != "checkpointed":
            raise HandoffError("handoff is not checkpointed; recovery must not restart a turn")
        status = hub.status(team)
        reason = None if self._source_matches(journal, status) else "current provider binding no longer matches the planned handoff"
        reason = reason or self._checkpoint_reason(status)
        if reason:
            self._event(journal, "execute-blocked", reason=reason)
            self._save(team, journal)
            return {"started": False, "reason": "requires stopped checkpoint: " + reason, "handoff": self.describe(team)}
        try:
            rotated = hub.rotate_idle_binding(team, journal["to"]["provider"], journal["to"]["model"], journal["id"])
            if not isinstance(rotated, dict) or not rotated.get("rotated"):
                raise HandoffError("hub did not confirm a quiesced binding rotation")
            journal["phase"] = "rotated"
            journal["rotation"] = {"oldSessionId": rotated.get("oldSessionId"), "newBindingSeq": rotated.get("bindingSeq")}
            self._event(journal, "binding-rotated", oldSeq=status.get("lastEventSeq"))
            self._save(team, journal)
            project = rotated.get("project")
            work_mode = rotated.get("workMode", "plan")
            result = hub.start(team, project, resume_prompt, journal["to"]["model"], provider=journal["to"]["provider"], work_mode=work_mode)
            journal["phase"] = "started"
            journal["tokenEpochs"].append({"provider": journal["to"]["provider"], "model": journal["to"]["model"], "reportedTokens": None})
            self._event(journal, "new-session-started", newSessionId=result.get("sessionId") if isinstance(result, dict) else None)
            self._save(team, journal)
            return {"started": True, "result": result, "handoff": self.describe(team)}
        except Exception as exc:
            journal["phase"] = "failed" if journal.get("phase") == "checkpointed" else journal.get("phase")
            self._event(journal, "start-failed", error=type(exc).__name__)
            self._save(team, journal)
            raise HandoffError("handoff did not start; inspect the retained journal before manual recovery") from exc

    def describe(self, team: str) -> dict[str, Any]:
        journal = self._read(team)
        if not journal:
            return {"active": False}
        return {"active": journal["phase"] not in {"started", "failed"}, "id": journal["id"], "phase": journal["phase"], "from": dict(journal["from"]), "to": dict(journal["to"]), "timeline": list(journal["timeline"])}
