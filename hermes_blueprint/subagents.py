"""Fresh-context subagents for the verifier, the planner and the optional red team.

The plugin, not the model, assembles each subagent's context packet, so brainstorm chatter never
leaks into the judgment. Launches go through ``ctx.subagent_lifecycle`` (works from a tool handler
during a turn, per-launch model and provider, narrowed toolsets; see DECISIONS D7). When the host
cannot launch one, the caller gets ``ok=False`` with the reason and records that the independent
pass did not run.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Job:
    role: str                      # verifier | planner | redteam
    project_id: int
    goal: str
    context: str
    toolsets: tuple[str, ...] = ()
    timeout_s: float = 600.0


@dataclass
class Outcome:
    ok: bool
    text: str = ""
    error: str = ""
    model: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


Runner = Callable[[Job], Outcome]


def unavailable(reason: str) -> Runner:
    def run(job: Job) -> Outcome:
        return Outcome(False, error=reason)
    return run


def lifecycle_runner(ctx: Any) -> Runner:
    """A runner backed by ``ctx.subagent_lifecycle``. Model and provider per role come from the
    plugin settings ``<role>_model`` / ``<role>_provider`` (empty = the user's main model)."""

    def run(job: Job) -> Outcome:
        service = getattr(ctx, "subagent_lifecycle", None)
        if service is None:
            return Outcome(False, error="this Hermes has no subagent_lifecycle")
        try:
            from agent.subagent_lifecycle import SubagentLaunchRequest
        except ImportError as exc:
            return Outcome(False, error=f"subagent API unavailable: {exc}")
        model = _setting(ctx, f"{job.role}_model")
        provider = _setting(ctx, f"{job.role}_provider")
        request = SubagentLaunchRequest(
            goal=job.goal, context=job.context, role="leaf", model=model or None,
            provider=provider or None, allowed_toolsets=job.toolsets or None,
            correlation_id=f"blueprint:{job.project_id}:{job.role}:{uuid.uuid4().hex[:10]}")
        try:
            handle = service.launch(request)
            service.wait(handle, timeout_seconds=job.timeout_s)
            result = service.result(handle)
        except Exception as exc:  # unknown provider, no active turn, ...
            return Outcome(False, error=f"{type(exc).__name__}: {exc}")
        state = str(getattr(result, "terminal_state", ""))
        summary = getattr(result, "summary", "") or ""
        label = "/".join(x for x in (provider, model) if x) or "main model"
        if "SUCCEEDED" not in state.upper():
            message = getattr(result, "error_message", "") or summary or state
            return Outcome(False, text=summary, error=f"{state}: {message}"[:500], model=label)
        return Outcome(True, text=summary, model=label,
                       meta={"usage": dict(getattr(result, "usage_metadata", None) or {})})

    return run


def _setting(ctx: Any, key: str) -> str:
    try:
        value = ctx.get_config(key, "")
    except Exception:
        return ""
    return str(value or "").strip()
