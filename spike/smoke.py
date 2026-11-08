"""Smoke test against a real Hermes, without a model turn: load hermes-blueprint through Hermes'
own plugin manager, then drive the registered /idea command and idea_* tools through the real
tool registry (real web_search / web_extract backends, real plugin storage).

Usage (from the hermes-agent checkout, with Hermes' own Python; see spike/RUN.md):
    python <repo>/spike/smoke.py
The plugin folder must be linked as $HERMES_HOME/plugins/hermes-blueprint. Nothing in the user's
config changes; the plugin is enabled for this process only. Kanban is not touched.
"""
from __future__ import annotations

import json
import sys
import uuid

PLUGIN = "hermes-blueprint"


def main() -> int:
    sys._hermes_relaunched = True
    import hermes_cli.plugins as plugins

    original = plugins._get_enabled_plugins

    def enabled():
        found = original()
        return (set(found) if found is not None else set()) | {PLUGIN}

    plugins._get_enabled_plugins = enabled
    plugins.discover_plugins(force=True)
    manager = plugins.get_plugin_manager()
    state = {k: (p.enabled, p.error) for k, p in manager._plugins.items() if PLUGIN in k}
    print("plugin:", state)
    command = manager._plugin_commands["idea"]["handler"]
    skills = [k for k in manager._plugin_skills if k.startswith(PLUGIN)]
    print("skills:", skills)

    import model_tools  # noqa: F401  (loads the built-in tools, as an agent turn does)
    from tools.registry import registry

    session = f"smoke-{uuid.uuid4().hex[:8]}"

    def tool(name: str, **args) -> dict:
        out = json.loads(registry.dispatch(name, args, session_id=session))
        print(f"\n> {name} {args.get('action')}:",
              json.dumps(out, ensure_ascii=False)[:700])
        return out

    print(command("start Smoke test: a Hermes plugin that turns ideas into plans",
                  session_id=session))
    tool("idea_phase", action="record", kind="brief", content={"who": "smoke"})
    tool("idea_profile", action="set", profile={"team": "solo", "agents": ["hermes"],
                                                "hours_per_day": 5})
    tool("idea_profile", action="confirm")
    tool("idea_phase", action="advance")
    tool("idea_research", action="plan", tier="quick", kind="software",
         questions=["what exists", "who uses it", "how hard"])
    found = tool("idea_research", action="search", purpose="background",
                 query="Hermes Agent kanban multi-agent board documentation")
    url = next((r["url"] for r in found.get("results", []) if "nousresearch" in r["url"]),
               "https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban")
    page = tool("idea_research", action="fetch", urls=[url])
    text = page["pages"][0].get("text", "")
    words = text.split()
    quote = " ".join(words[len(words) // 3:len(words) // 3 + 10])
    claim = tool("idea_research", action="claim", text="Hermes has a kanban board (smoke)",
                 type="technical", evidence=[{"source": page["pages"][0]["source"],
                                              "quote": quote}])
    hook = [cb for name, cb in manager._hooks.items() if name == "pre_llm_call"]
    print("\nstate card hooks:", len(hook))
    print(command("status", session_id=session))
    print(command("stop", session_id=session))
    ok = bool(claim.get("ok")) and claim.get("label") == "✅"
    print("\nSMOKE", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
