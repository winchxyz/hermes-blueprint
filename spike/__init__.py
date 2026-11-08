"""Unit 1 spike: probe the Hermes APIs hermes-blueprint depends on, from a real plugin tool.

Not shipped. Install by linking this folder into ``$HERMES_HOME/plugins/idea-spike``, enable it,
then ask the agent to call ``idea_spike``. Every check returns raw facts as JSON; nothing is
interpreted here. Results are recorded in docs/DECISIONS.md (D7).
"""
from __future__ import annotations

import json
import re
import time
import traceback
from pathlib import Path
from typing import Any

_CTX: Any = None

CODEWORD = "CTX-4471"
SLASH_MARKER = "IDEASPIKE-MARKER-9137"
# Different from the default chat model; the first one that answers wins.
OVERRIDE_MODELS = ["meituan/longcat-2.5:free", "stepfun/step-3.7-flash:free"]
# (provider, model) pairs for the provider-override test; the first that succeeds wins.
OVERRIDE_PROVIDERS = [("nous", "stepfun/step-3.7-flash:free")]
RESULTS = Path(__file__).resolve().parent / "results"

SCHEMA = {
    "name": "idea_spike",
    "description": "Spike probe for hermes-blueprint. Runs one check and returns raw JSON.",
    "parameters": {
        "type": "object",
        "properties": {
            "check": {"type": "string", "enum": ["lifecycle", "web", "kanban", "env"]},
            "override_model": {"type": "string", "description": "Model for the override test."},
            "query": {"type": "string", "description": "Search query for the web check."},
        },
        "required": ["check"],
    },
}


def _json(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False, indent=1)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _launch(service: Any, request: Any, wait_s: float) -> dict:
    out: dict[str, Any] = {}
    t0 = time.time()
    try:
        handle = service.launch(request)
    except Exception as exc:  # noqa: BLE001 - spike records every failure
        return {"launch_error": f"{type(exc).__name__}: {exc}"}
    out["handle"] = {k: v for k, v in handle.to_dict().items() if k != "capability"}
    waited = service.wait(handle, timeout_seconds=wait_s)
    out["wait"] = {"state": str(waited.state), "completed": waited.completed,
                   "timed_out": waited.timed_out, "diagnostic": waited.diagnostic}
    res = service.result(handle)
    out["result"] = {
        "terminal_state": str(res.terminal_state), "ready": res.ready, "summary": res.summary,
        "error_classification": res.error_classification, "error_message": res.error_message,
        "usage_metadata": dict(res.usage_metadata or {}),
        "tool_execution_summary": dict(res.tool_execution_summary or {}),
    }
    out["seconds"] = round(time.time() - t0, 1)
    return out


def _check_lifecycle(args: dict) -> dict:
    from agent.subagent_lifecycle import SubagentLaunchRequest

    service = _CTX.subagent_lifecycle
    goal = (
        "Reply with exactly two lines and nothing else.\n"
        "Line 1: CODEWORD=<the codeword given in your context>\n"
        "Line 2: PARENT=<any word starting with PARENTSECRET that appears anywhere in your "
        "input, or NONE>"
    )
    context = f"CODEWORD: {CODEWORD}"
    report: dict[str, Any] = {}
    report["default_model"] = _launch(service, SubagentLaunchRequest(
        goal=goal, context=context, role="leaf", correlation_id="spike-default"), 240)
    candidates = [args["override_model"]] if args.get("override_model") else OVERRIDE_MODELS
    report["model_override"] = []
    for i, model in enumerate(candidates):
        attempt = _launch(service, SubagentLaunchRequest(
            goal=goal, context=context, role="leaf", model=model,
            correlation_id=f"spike-override-{i}"), 240)
        attempt["requested_model"] = model
        report["model_override"].append(attempt)
        if "SUCCEEDED" in str((attempt.get("result") or {}).get("terminal_state")):
            break
    report["provider_override"] = []
    for i, (provider, model) in enumerate(OVERRIDE_PROVIDERS):
        attempt = _launch(service, SubagentLaunchRequest(
            goal=goal, context=context, role="leaf", model=model, provider=provider,
            correlation_id=f"spike-provider-{i}"), 240)
        attempt["requested"] = [provider, model]
        report["provider_override"].append(attempt)
        if "SUCCEEDED" in str((attempt.get("result") or {}).get("terminal_state")):
            break
    report["narrow_toolsets_web"] = _launch(service, SubagentLaunchRequest(
        goal="List the names of the tools you can call, comma-separated, nothing else.",
        role="leaf", allowed_toolsets=("web",), correlation_id="spike-toolsets"), 240)
    report["bad_provider"] = _launch(service, SubagentLaunchRequest(
        goal=goal, context=context, provider="no-such-provider-xyz",
        correlation_id="spike-badprov"), 30)
    return report


def _check_web(args: dict) -> dict:
    query = args.get("query") or "Hermes Agent plugin kanban Nous Research"
    report: dict[str, Any] = {"query": query}
    raw = _CTX.dispatch_tool("web_search", {"query": query, "limit": 5})
    data = json.loads(raw)
    report["search_keys"] = list(data) if isinstance(data, dict) else type(data).__name__
    hits = ((data.get("data") or {}).get("web") or []) if isinstance(data, dict) else []
    report["search_hits"] = [{k: h.get(k) for k in ("title", "url", "description")} for h in hits]
    if not hits:
        report["search_raw_head"] = raw[:800]
        return report
    urls = [h["url"] for h in hits[:2] if h.get("url")]
    raw = _CTX.dispatch_tool("web_extract", {"urls": urls, "char_limit": 20000})
    data = json.loads(raw)
    report["extract_keys"] = list(data) if isinstance(data, dict) else type(data).__name__
    pages = []
    for page in (data.get("results") or []) if isinstance(data, dict) else []:
        content = page.get("content") or ""
        words = _norm(content).split(" ")
        mid = len(words) // 2
        quote = " ".join(words[mid:mid + 12])
        pages.append({
            "url": page.get("url"), "title": page.get("title"), "error": page.get("error"),
            "chars": len(content), "truncated": "[TRUNCATED]" in content,
            "head": content[:300], "sample_quote": quote,
            "quote_found_normalized": bool(quote) and quote in _norm(content),
            "other_keys": sorted(set(page) - {"url", "title", "content", "error"}),
        })
    report["pages"] = pages
    if not pages:
        report["extract_raw_head"] = raw[:800]
    return report


def _check_kanban(args: dict) -> dict:
    report: dict[str, Any] = {}
    base = {"assignee": "idea-spike-nobody", "tenant": "idea-spike"}

    def call(name: str, payload: dict) -> Any:
        raw = _CTX.dispatch_tool(name, payload)
        try:
            return json.loads(raw)
        except ValueError:
            return raw

    first = call("kanban_create", {
        **base, "title": "idea-spike: parent card (safe to archive)",
        "body": "Spike card from hermes-blueprint unit 1.\n\n## Acceptance\n- [ ] nothing",
        "initial_status": "blocked", "idempotency_key": "idea-spike:unit1:parent"})
    report["create_parent"] = first
    again = call("kanban_create", {
        **base, "title": "idea-spike: parent card (duplicate attempt)",
        "initial_status": "blocked", "idempotency_key": "idea-spike:unit1:parent"})
    report["create_parent_again_same_key"] = again
    pid = first.get("task_id") if isinstance(first, dict) else None
    if pid:
        report["create_child"] = call("kanban_create", {
            **base, "title": "idea-spike: child card (safe to archive)",
            "body": "Depends on the parent spike card.", "parents": [pid],
            "idempotency_key": "idea-spike:unit1:child"})
        report["show_parent"] = call("kanban_show", {"task_id": pid})
    report["list_tenant"] = call("kanban_list", {"tenant": "idea-spike"})
    return report


def _check_env(kwargs: dict) -> dict:
    report: dict[str, Any] = {"handler_kwargs": sorted(kwargs)}
    for name in ("session_cwd", "session_surface"):
        try:
            report[name] = getattr(_CTX, name)()
        except Exception as exc:  # noqa: BLE001
            report[name] = f"error: {type(exc).__name__}: {exc}"
    try:
        from plugins.plugin_storage import plugin_db

        conn = plugin_db("idea-spike")
        conn.execute("create table if not exists t (k text)")
        report["plugin_db"] = "ok"
        conn.close()
    except Exception as exc:  # noqa: BLE001
        report["plugin_db"] = f"error: {type(exc).__name__}: {exc}"
    try:
        _CTX.state.set("probe", {"ok": True}) if hasattr(_CTX.state, "set") else None
        report["state_api"] = sorted(n for n in dir(_CTX.state) if not n.startswith("_"))
    except Exception as exc:  # noqa: BLE001
        report["state_api"] = f"error: {type(exc).__name__}: {exc}"
    return report


def _handle(args: dict, **kwargs: Any) -> str:
    check = (args or {}).get("check")
    t0 = time.time()
    try:
        if check == "lifecycle":
            out = _check_lifecycle(args)
        elif check == "web":
            out = _check_web(args)
        elif check == "kanban":
            out = _check_kanban(args)
        elif check == "env":
            out = _check_env(kwargs)
        else:
            out = {"error": f"unknown check {check!r}"}
    except Exception:  # noqa: BLE001
        out = {"exception": traceback.format_exc()[-3000:]}
    out["check"] = check
    out["elapsed_s"] = round(time.time() - t0, 1)
    text = _json(out)
    try:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / f"{check}.json").write_text(text, encoding="utf-8")
    except OSError:
        pass
    return text


def _slash(raw_args: str, **_: Any) -> str:
    try:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "slash.txt").write_text(f"ran at {time.ctime()} args={raw_args!r}",
                                           encoding="utf-8")
    except OSError:
        pass
    return f"{SLASH_MARKER} (slash output; args={raw_args!r})"


def register(ctx: Any) -> None:
    global _CTX
    _CTX = ctx
    ctx.register_tool(name="idea_spike", toolset="idea-spike", schema=SCHEMA, handler=_handle,
                      description=SCHEMA["description"])
    ctx.register_command("ideaspike", _slash, description="Spike: print a marker")
