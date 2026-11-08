"""Shared fixtures: a fake Hermes ctx and a store on a temporary SQLite file. No network."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from hermes_blueprint.store import Store  # noqa: E402


class FakeCtx:
    """Records register_* calls like Hermes' PluginContext."""

    def __init__(self, config: dict | None = None) -> None:
        self.tools: dict[str, dict] = {}
        self.hooks: list[tuple[str, object]] = []
        self.commands: dict[str, dict] = {}
        self.skills: list[dict] = []
        self.config = dict(config or {})
        self.dispatched: list[tuple[str, dict]] = []

    def register_tool(self, name, toolset, schema, handler, check_fn=None, requires_env=None,
                      is_async=False, description="", emoji="", override=False):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler}

    def register_hook(self, hook_name, callback, *, hold_stream=False):
        self.hooks.append((hook_name, callback))

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = {"handler": handler, "description": description,
                               "args_hint": args_hint}

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills.append({"name": name, "path": Path(path), "description": description})

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    # optional host APIs used by the handoff and the method skill
    blueprints: list = []
    backend = None
    choice = None

    def register_automation_blueprint(self, key, **fields):
        self.blueprints = [*self.blueprints, {"key": key, **fields}]

    def dispatch_tool(self, name, args):
        self.dispatched.append((name, args))
        if self.backend is None:
            raise RuntimeError("no fake backend")
        return self.backend(name, args)

    def ask_choice(self, question, choices):
        return self.choice

    def session_cwd(self):
        return ""


class FakeHermes:
    """Fake web_search / web_extract / kanban_* backends, recording calls."""

    def __init__(self) -> None:
        self.pages: dict[str, tuple[str, str]] = {}     # url -> (title, content)
        self.search_results: dict[str, list[dict]] = {}  # query substring -> hits
        self.tasks: dict[str, dict] = {}
        self.keys: dict[str, str] = {}

    def page(self, url: str, content: str, title: str = "") -> None:
        self.pages[url] = (title or url, content)

    def __call__(self, name: str, args: dict) -> str:
        import json

        if name == "web_search":
            hits = []
            for needle, found in self.search_results.items():
                if needle in args["query"]:
                    hits = found
            return json.dumps({"success": True, "data": {"web": hits}})
        if name == "web_extract":
            out = []
            for url in args["urls"]:
                if url in self.pages:
                    title, content = self.pages[url]
                    out.append({"url": url, "title": title, "content": content, "error": None})
                else:
                    out.append({"url": url, "title": "", "content": "", "error": "404"})
            return json.dumps({"results": out})
        if name == "kanban_create":
            key = args.get("idempotency_key")
            if key in self.keys:
                tid = self.keys[key]
                return json.dumps({"ok": True, "task_id": tid,
                                   "status": self.tasks[tid]["status"]})
            tid = f"t_{len(self.tasks) + 1:04d}"
            status = args.get("initial_status") or ("todo" if args.get("parents") else "ready")
            self.tasks[tid] = {**args, "id": tid, "status": status, "started_at": None,
                               "completed_at": None}
            if key:
                self.keys[key] = tid
            return json.dumps({"ok": True, "task_id": tid, "status": status})
        if name == "kanban_show":
            task = self.tasks.get(args["task_id"])
            return json.dumps({"task": task} if task else {"error": "no task"})
        raise AssertionError(f"unexpected tool {name}")


class FakeRunner:
    """Stands in for the subagent lifecycle: returns canned replies per role."""

    def __init__(self, replies: dict | None = None, fail: str = "") -> None:
        self.replies = dict(replies or {})
        self.fail = fail
        self.jobs: list = []

    def __call__(self, job):
        from hermes_blueprint.subagents import Outcome

        self.jobs.append(job)
        if self.fail:
            return Outcome(False, error=self.fail)
        reply = self.replies.get(job.role)
        if callable(reply):
            reply = reply(job)
        return Outcome(True, text=reply or "", model="fake/model")


class Clock:
    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        self.now += 1.0
        return self.now


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "data.db"
    return Store(lambda: sqlite3.connect(db), clock=Clock())


@pytest.fixture
def fake_ctx():
    return FakeCtx()


TODAY = __import__("datetime").date(2026, 11, 9)

PAGE_A = ("Padel is the fastest-growing sport in Spain. Club bookings rose 40% in 2025, "
          "according to the federation's annual report. Most clubs still take bookings by "
          "phone or WhatsApp.")
PAGE_B = ("Industry survey: court bookings at padel clubs rose 40% in 2025, with most clubs "
          "relying on phone calls.")
PAGE_C = "Playtomic lets players book padel courts online in 40 countries."


class Harness:
    """The registered plugin with fake Hermes backends, driven like the agent would."""

    def __init__(self, store, runner=None) -> None:
        from hermes_blueprint import register

        self.store = store
        self.web = FakeHermes()
        self.runner = runner or FakeRunner()
        self.ctx = FakeCtx()
        self.ctx.backend = self.web
        register(self.ctx, store_factory=lambda: store, runner=self.runner)
        self.set_today(TODAY)
        self.web.page("https://fep.es/report", PAGE_A, "Federation report")
        self.web.page("https://survey.example.org/padel", PAGE_B, "Survey")
        self.web.page("https://mirror.example.net/report", PAGE_A, "Mirror of the report")
        self.web.page("https://playtomic.io", PAGE_C, "Playtomic")

    def set_today(self, day) -> None:
        for name in ("idea_verdict", "idea_recheck"):
            self.ctx.tools[name]["handler"]._today = lambda day=day: day

    def call(self, tool: str, session: str = "s1", **args) -> dict:
        import json

        return json.loads(self.ctx.tools[tool]["handler"](args, session_id=session))

    def idea(self, text: str, session: str = "s1") -> str:
        return self.ctx.commands["idea"]["handler"](text, session_id=session)

    def ok(self, tool: str, **args) -> dict:
        res = self.call(tool, **args)
        assert res["ok"], res
        return res

    def project(self):
        return self.store.bound_project("s1")

    # walking the phases with real tools ------------------------------------------------------

    def phase1(self) -> None:
        self.idea("start A booking assistant for padel clubs")
        self.ok("idea_phase", action="record", kind="brief", content={"who": "club owners"})
        self.ok("idea_profile", action="set", profile={
            "team": "solo", "agents": ["hermes", "claude-code"], "hours_per_day": 5,
            "parallel_agents": 2})
        self.ok("idea_profile", action="confirm", assumed=["days_per_week"])
        self.ok("idea_phase", action="advance")

    def research(self, verify_reply: str | None = None) -> dict:
        self.gather(verify_reply)
        return self.ok("idea_research", action="briefing",
                       summary="Bookings grow [C1]; Playtomic exists [C2]; phones rule [C3].",
                       unknowns=["club willingness to pay"])

    def gather(self, verify_reply: str | None = None) -> dict:
        self.ok("idea_research", action="plan", tier="quick", kind="software",
                questions=["who books", "what exists", "can we integrate"])
        for q in ("padel booking failed", "why not padel booking app"):
            self.ok("idea_research", action="search", query=q, purpose="disconfirm")
        for ch in ("github", "registries", "marketplaces"):
            self.ok("idea_research", action="search", query=f"padel booking {ch}",
                    purpose="competitor", channel=ch)
        self.ok("idea_research", action="fetch", urls=["https://fep.es/report",
                                                       "https://survey.example.org/padel",
                                                       "https://playtomic.io"])
        self.ok("idea_research", action="claim", text="Padel club bookings rose 40% in 2025",
                type="market_size", contested=True, evidence=[
                    {"source": "S1", "quote": "Club bookings rose 40% in 2025"},
                    {"source": "S2", "quote": "court bookings at padel clubs rose 40% in 2025"}])
        self.ok("idea_research", action="claim", text="Playtomic books courts online",
                type="competitor_exists",
                evidence=[{"source": "S3", "quote": "book padel courts online in 40 countries"}])
        self.ok("idea_research", action="claim", text="Most clubs book by phone",
                type="other", evidence=[{"source": "S1",
                                         "quote": "Most clubs still take bookings by phone"}])
        self.runner.replies["verifier"] = verify_reply or (
            '{"claims": [{"id": "C1", "verdict": "supported", "original": true}, '
            '{"id": "C2", "verdict": "supported", "original": true}, '
            '{"id": "C3", "verdict": "supported", "original": true}]}')
        return self.ok("idea_research", action="verify")

    def to_phase5(self) -> None:
        self.phase1()
        self.research()
        self.ok("idea_phase", action="advance")
        self.ok("idea_phase", action="record", kind="variants", content=[
            {"name": "WhatsApp bot", "summary": "a"}, {"name": "Web app", "summary": "b"},
            {"name": "Plugin", "summary": "c"}])
        self.ok("idea_phase", action="advance")
        self.ok("idea_phase", action="record", kind="choice",
                content={"variant": "WhatsApp bot", "reason": "clubs live in WhatsApp"})
        self.ok("idea_phase", action="advance")

    def verdict_args(self, **over) -> dict:
        args = {
            "action": "commit", "verdict": "go_with_conditions",
            "thesis": "Clubs will pay for a bot that fills empty court slots.",
            "reference_class": {"name": "Chrome extensions", "base_rate": "87% < 1k installs",
                                "source": "chrome_extensions"},
            "p_success": 0.3,
            "premortem": [{"cause": "no distribution", "p_given_failure": 0.4},
                          {"cause": "clubs will not pay", "p_given_failure": 0.35},
                          {"cause": "WhatsApp API approval", "p_given_failure": 0.15}],
            "must_be_true": [{"assumption": "clubs pay", "test": "3 pilot clubs",
                              "cost": "2 days", "deadline": "2027-01-31",
                              "kill_threshold": "0 of 3 pay"}],
            "tripwires": [{"metric": "paying clubs", "threshold": ">= 1", "by": "2027-02-28"}],
            "builder_fit": "solo with agents; no sales experience",
            "estimate_realism": "bot is hours; WhatsApp approval is the wait",
            "predictions": [
                {"statement": "1 club pays by Feb", "p": 0.35, "resolve_by": "2027-02-28",
                 "how": "bank"},
                {"statement": "API approved in 2 weeks", "p": 0.6, "resolve_by": "2027-01-15",
                 "how": "Meta dashboard"},
                {"statement": "MVP live by Dec 15", "p": 0.7, "resolve_by": "2026-12-15",
                 "how": "bot answers"}],
        }
        args.update(over)
        return args


@pytest.fixture
def bp(store):
    return Harness(store)
