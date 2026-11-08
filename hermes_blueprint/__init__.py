"""hermes-blueprint: turn a raw idea into a plan you can build, inside Hermes.

Six phases (Understanding, Context, Generation, Deep dive, Critique, Plan) whose exit gates are
checked in code against stored artifacts.
"""
from __future__ import annotations

from typing import Any

__version__ = "0.0.1"

PLUGIN_NAME = "hermes-blueprint"
TOOLSET = "blueprint"


def _default_store():
    """The plugin's own SQLite database under ``<hermes home>/plugin-data/``.

    Opened lazily on first use, never at registration (Plugin Doctor runs ``register`` with the
    network blocked and expects no side effects).
    """
    from plugins.plugin_storage import plugin_db

    from .store import Store

    return Store(lambda: plugin_db(PLUGIN_NAME))


def register(ctx: Any, store_factory=None) -> None:
    """Register the ``/idea`` command and the ``idea_phase`` tool."""
    from .commands import IdeaCommand
    from .tools import IDEA_PHASE_SCHEMA, IdeaPhaseTool

    holder: dict[str, Any] = {}

    def store():
        if "store" not in holder:
            holder["store"] = (store_factory or _default_store)()
        return holder["store"]

    ctx.register_command(
        "idea", IdeaCommand(store), description="Blueprint: turn a raw idea into a buildable plan",
        args_hint="start <idea> | status | phase [n] | list | resume <id> | log | stop")
    ctx.register_tool(
        name="idea_phase", toolset=TOOLSET, schema=IDEA_PHASE_SCHEMA,
        handler=IdeaPhaseTool(store), description=IDEA_PHASE_SCHEMA["description"], emoji="💡")
