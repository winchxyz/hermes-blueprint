"""hermes-blueprint: turn a raw idea into a plan you can build, inside Hermes.

Six phases (Understanding, Context, Generation, Deep dive, Critique, Plan) whose exit gates are
checked in code against stored artifacts, with the quality harness enforced by tools: a research
ledger with quote checks, a pre-committed critic verdict, a validated A/H/W plan, a kanban
handoff and scored re-checks.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

__version__ = "0.2.1"

PLUGIN_NAME = "hermes-blueprint"
TOOLSET = "blueprint"
SKILLS_DIR = Path(__file__).resolve().parent / "skills"


def _default_store():
    """The plugin's own SQLite database under ``<hermes home>/plugin-data/``.

    Opened lazily on first use, never at registration (Plugin Doctor runs ``register`` with the
    network blocked and expects no side effects).
    """
    from plugins.plugin_storage import plugin_db

    from .store import Store

    return Store(lambda: plugin_db(PLUGIN_NAME))


def make_state_hook(store_factory):
    """``pre_llm_call``: a short state card while this chat has an active blueprint project;
    ``None`` (no tokens) for every other chat. Never raises."""
    from .guide import state_card

    def hook(session_id: str = "", turn_id: str = "", **_: Any):
        if not session_id:
            return None
        try:
            store = store_factory()
            project = store.bound_project(session_id)
            if project is None or project.status not in ("active", "planned"):
                return None
            if project.status == "active":
                # Count the user's turn in this phase: gates that need the user check it.
                store.record_turn(project.id, project.phase, str(turn_id or store.now()))
            return {"context": state_card(store, project)}
        except Exception:
            return None

    return hook


def register(ctx: Any, store_factory=None, runner=None) -> None:
    """Register the ``/idea`` command, the ``idea_*`` tools, the state-card hook, the method
    skill and the weekly re-check blueprint."""
    from .commands import IdeaCommand
    from .planning import PLAN_SCHEMA, PlanTool
    from .profile import PROFILE_SCHEMA, ProfileTool
    from .recheck import RECHECK_SCHEMA, RecheckTool
    from .research import RESEARCH_SCHEMA, ResearchTool
    from .subagents import lifecycle_runner
    from .tools import IDEA_PHASE_SCHEMA, IdeaPhaseTool
    from .verdict import VERDICT_SCHEMA, VerdictTool

    holder: dict[str, Any] = {}

    def store():
        if "store" not in holder:
            holder["store"] = (store_factory or _default_store)()
        return holder["store"]

    def dispatch(name: str, args: dict) -> str:
        return ctx.dispatch_tool(name, args)

    run = runner or lifecycle_runner(ctx)

    ctx.register_command(
        "idea", IdeaCommand(store, ctx),
        description="Blueprint: turn a raw idea into a buildable plan",
        args_hint="start <idea> | status | phase [n] | list | resume <id> | log | stop | "
                  "profile | handoff | recheck | ledger")
    tools = [
        (IDEA_PHASE_SCHEMA, IdeaPhaseTool(store), "💡"),
        (PROFILE_SCHEMA, ProfileTool(store), "🧑"),
        (RESEARCH_SCHEMA, ResearchTool(store, dispatch, run), "🔎"),
        (VERDICT_SCHEMA, VerdictTool(store, run), "⚖️"),
        (PLAN_SCHEMA, PlanTool(store, run), "📐"),
        (RECHECK_SCHEMA, RecheckTool(store, dispatch), "📊"),
    ]
    for schema, handler, emoji in tools:
        ctx.register_tool(name=schema["name"], toolset=TOOLSET, schema=schema, handler=handler,
                          description=schema["description"], emoji=emoji)
    ctx.register_hook("pre_llm_call", make_state_hook(store))

    skill = SKILLS_DIR / "blueprint" / "SKILL.md"
    if skill.exists() and hasattr(ctx, "register_skill"):
        ctx.register_skill("blueprint", skill,
                           description="Blueprint method: idea to buildable plan in 6 phases")

    register_blueprint = getattr(ctx, "register_automation_blueprint", None)
    if register_blueprint is not None:
        try:
            register_blueprint(
                "recheck", title="Blueprint weekly re-check",
                description="Every week: kanban progress, due predictions and estimate vs "
                            "actual for a planned blueprint project.",
                schedule_template="0 9 * * 1",
                prompt_template=(
                    "Re-check my blueprint projects. Call idea_recheck(action=overview), then "
                    "action=report for each planned project with work due. List the predictions "
                    "that are due and the units whose actual hours are missing, and ask me for the "
                    "outcomes. Then say whether the data disconfirms the thesis or only the "
                    "tuning."),
                category="productivity", skills=[f"{PLUGIN_NAME}:blueprint"],
                tags=["blueprint", "planning", "recheck"])
        except Exception:  # an older or stricter host: the /idea recheck command still works
            pass
