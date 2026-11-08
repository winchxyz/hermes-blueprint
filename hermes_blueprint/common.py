"""Shared plumbing for the model-facing tools.

Every tool handler follows the Hermes contract: it takes ``(args, **kwargs)``, returns a JSON
string and never raises into the agent loop. Tools are bound to the project of the calling chat
(``session_id`` from the handler kwargs).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from .store import Project, Store

NO_PROJECT = ("No blueprint project in this chat. Ask the user to run /idea start <idea> "
              "or /idea resume <id>.")


class ToolError(Exception):
    """Raised inside an action to return ``{"ok": false, "error": ...}`` plus extra fields."""

    def __init__(self, message: str, **data: Any) -> None:
        super().__init__(message)
        self.data = data


def ok(**data: Any) -> str:
    return json.dumps({"ok": True, **data}, ensure_ascii=False, default=str)


def err(message: str, **data: Any) -> str:
    return json.dumps({"ok": False, "error": message, **data}, ensure_ascii=False, default=str)


def session_key(kwargs: dict) -> str:
    return str(kwargs.get("session_id") or kwargs.get("session_key") or "")


class BoundTool:
    """Base for ``idea_*`` tools: resolves the chat's project and dispatches ``act_<action>``."""

    needs_project = True

    def __init__(self, store_factory: Callable[[], Store]) -> None:
        self._store_factory = store_factory

    def actions(self) -> list[str]:
        return sorted(n[4:] for n in dir(self) if n.startswith("act_"))

    def __call__(self, args: dict, **kwargs: Any) -> str:
        try:
            args = args or {}
            store = self._store_factory()
            project = store.bound_project(session_key(kwargs))
            if project is None and self.needs_project:
                return err(NO_PROJECT)
            action = str(args.get("action") or "")
            handler = getattr(self, f"act_{action}", None)
            if handler is None:
                return err(f"unknown action {action!r}", actions=self.actions())
            return ok(**handler(store, project, args))
        except ToolError as exc:
            return err(str(exc), **exc.data)
        except Exception as exc:  # never raise into the agent loop
            return err(f"{type(exc).__name__}: {exc}")


def require_phase(project: Project, *allowed: int, what: str) -> None:
    from .phases import phase_name

    if project.status != "active" and project.status != "planned":
        raise ToolError(f"project is {project.status}")
    if project.phase not in allowed:
        names = ", ".join(phase_name(p) for p in allowed)
        raise ToolError(f"{what} belongs to phase {names}; the project is in "
                        f"{phase_name(project.phase)}")


def parse_ref(ref: Any, prefix: str) -> int:
    """'C12', 'c12', 12 or '12' -> 12."""
    text = str(ref).strip()
    m = re.fullmatch(rf"(?i){prefix}?(\d+)", text)
    if not m:
        raise ToolError(f"expected an id like {prefix}1, got {ref!r}")
    return int(m.group(1))


def extract_json(text: str) -> Any:
    """First JSON object or array in a model's reply (fenced or bare)."""
    if not text:
        raise ValueError("empty reply")
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(text)
    for chunk in candidates:
        chunk = chunk.strip()
        try:
            return json.loads(chunk)
        except ValueError:
            pass
        for opener, closer in (("{", "}"), ("[", "]")):
            start, end = chunk.find(opener), chunk.rfind(closer)
            if 0 <= start < end:
                try:
                    return json.loads(chunk[start:end + 1])
                except ValueError:
                    continue
    raise ValueError("no JSON object found in the reply")
