"""Run one real Hermes agent turn in-process with the idea-spike plugin loaded.

Why: inside the Claude desktop app (an MSIX package) `hermes plugins enable` and the CLI's
gateway start fail, because writes to %LOCALAPPDATA% are virtualized. This harness skips both:
it uses Hermes' own plugin manager and AIAgent, adds idea-spike to the enabled set for this
process only, and resolves the model the same way cron does. Nothing in the user's config changes.

Usage (from the hermes-agent checkout, with Hermes' own Python):
    python <repo>/spike/harness.py "<prompt>" [<prompt> ...]
Several prompts run as consecutive turns of one conversation.
"""
from __future__ import annotations

import json
import sys
import time


def main(prompts: list[str]) -> None:
    # Run on the interpreter we were started with (Hermes' selected dependency environment).
    # Without this, Hermes' bootstrap may try to finish a pending source update and relaunch
    # into a fresh environment, which fails inside the MSIX sandbox.
    sys._hermes_relaunched = True
    import hermes_cli.plugins as plugins

    original = plugins._get_enabled_plugins

    def enabled_with_spike():
        found = original()
        return (set(found) if found is not None else set()) | {"idea-spike"}

    plugins._get_enabled_plugins = enabled_with_spike
    plugins.discover_plugins(force=True)
    manager = plugins.get_plugin_manager()
    loaded = {k: (p.enabled, p.error) for k, p in manager._plugins.items() if "spike" in k}
    print("plugin:", loaded, flush=True)

    from hermes_cli.runtime_provider import resolve_runtime_provider
    from run_agent import AIAgent

    runtime = resolve_runtime_provider(requested=None)
    from hermes_cli.config import load_config

    model = (load_config().get("model") or {}).get("default")
    print("model:", model, "provider:", runtime.get("provider"), flush=True)
    agent = AIAgent(
        model=model, api_key=runtime.get("api_key"), base_url=runtime.get("base_url"),
        provider=runtime.get("provider"), requested_provider=runtime.get("requested_provider"),
        api_mode=runtime.get("api_mode"), request_overrides=runtime.get("request_overrides"),
        quiet_mode=True, skip_memory=True, skip_context_files=True, platform="cli",
        max_iterations=30,
    )
    names = sorted(getattr(agent, "valid_tool_names", []) or [])
    print("session:", getattr(agent, "session_id", None), "| idea_spike visible:",
          "idea_spike" in names, "| tools:", len(names), flush=True)
    for prompt in prompts:
        t0 = time.time()
        reply = agent.chat(prompt)
        print(json.dumps({"prompt": prompt[:120], "seconds": round(time.time() - t0, 1),
                          "reply": reply}, ensure_ascii=False, indent=1), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
