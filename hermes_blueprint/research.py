"""Phase 2 research ledger (harness H1-H3): searches, fetched pages, claims, verifier, briefing.

The model never writes a ✅ itself. It logs searches, fetches pages (the plugin stores their
text), and records claims with exact quotes; code checks every quote against the stored text and
assigns the label from the evidence rules. The briefing that closes phase 2 is assembled here:
the model writes the summary, code appends the source log, the coverage and the Not verified block.
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any

from . import evidence
from .common import BoundTool, ToolError, extract_json, parse_ref, require_phase
from .store import Project, Store
from .subagents import Job, Runner

Dispatch = Callable[[str, dict], str]

PRODUCER = "idea_research"
PURPOSES = ("support", "disconfirm", "competitor", "background")
CHANNELS = ("github", "registries", "marketplaces", "app_stores", "product_hunt",
            "hacker_news", "reddit", "x", "web")
TIERS: dict[str, dict[str, Any]] = {
    "quick": {"min_claims": 3, "min_disconfirm": 2,
              "channels": ("github", "registries", "marketplaces")},
    "standard": {"min_claims": 6, "min_disconfirm": 2,
                 "channels": ("github", "registries", "marketplaces", "app_stores",
                              "product_hunt", "hacker_news", "reddit", "web")},
    "deep": {"min_claims": 10, "min_disconfirm": 3, "channels": CHANNELS},
}
DEFAULT_PLAN = {"tier": "standard", "kind": "software", "questions": []}
FETCH_CHAR_LIMIT = 60_000
RETURN_CHARS = 6_000

RESEARCH_SCHEMA: dict[str, Any] = {
    "name": "idea_research",
    "description": (
        "Blueprint research ledger for the idea in this chat (phase 2 Context, also later for "
        "new evidence). Snippets are leads, never evidence: search, fetch the page, then record "
        "a claim with an exact quote; code checks the quote and sets ✅/⚠️/🔍. Actions: plan "
        "(tier + questions), search (purpose support|disconfirm|competitor|background), fetch "
        "(urls -> S#), read (S# page text by offset or find), claim (text, type, evidence "
        "[{source, quote}]), absence (nothing-exists claim with the searches behind it), "
        "retract, verify (independent fresh-context check), briefing (closes phase 2), ledger."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": [
                "plan", "search", "fetch", "read", "claim", "absence", "retract", "verify",
                "briefing", "ledger"]},
            "tier": {"type": "string", "enum": list(TIERS),
                     "description": "plan: quick (personal project), standard, deep."},
            "kind": {"type": "string", "enum": ["software", "other"],
                     "description": "plan: software ideas need the competitor sweep."},
            "questions": {"type": "array", "items": {"type": "string"},
                          "description": "plan: 3-8 research questions from 4 perspectives "
                                         "(user/demand, competitors, feasibility, distribution)."},
            "query": {"type": "string", "description": "search: the query."},
            "purpose": {"type": "string", "enum": list(PURPOSES)},
            "channel": {"type": "string", "enum": list(CHANNELS),
                        "description": "search with purpose=competitor: which channel."},
            "urls": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "source": {"type": "string", "description": "read: S# id."},
            "find": {"type": "string", "description": "read: phrase to locate in the page."},
            "offset": {"type": "integer", "minimum": 0},
            "text": {"type": "string", "description": "claim/absence: one atomic claim."},
            "type": {"type": "string", "enum": list(evidence.CLAIM_TYPES)},
            "evidence": {
                "type": "array",
                "items": {"type": "object", "properties": {
                    "source": {"type": "string", "description": "S# id"},
                    "quote": {"type": "string", "description": "exact words from the page"}},
                    "required": ["source", "quote"]},
            },
            "contested": {"type": "boolean",
                          "description": "claim: numeric or disputed -> needs 2 independent."},
            "as_of": {"type": "string", "description": "claim: date the fact holds, YYYY-MM."},
            "unverified": {"type": "boolean",
                           "description": "claim: record a lead without evidence (🔍)."},
            "searches": {"type": "array", "items": {"type": "integer"},
                         "description": "absence: search ids that found nothing."},
            "claim": {"type": "string", "description": "retract: C# id."},
            "reason": {"type": "string"},
            "summary": {"type": "string",
                        "description": "briefing: the findings in prose, citing [C#] inline."},
            "surprises": {"type": "array", "items": {"type": "string"}},
            "unknowns": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["action"],
    },
}


# data access ---------------------------------------------------------------------------------

def research_plan(store: Store, project: Project) -> dict[str, Any]:
    art = store.latest(project.id, "research_plan")
    return dict(art.payload) if art else dict(DEFAULT_PLAN)


def searches(store: Store, project_id: int) -> list[dict[str, Any]]:
    with store.tx() as conn:
        rows = conn.execute("SELECT id, query, purpose, channel, results, at FROM searches"
                            " WHERE project_id = ? ORDER BY id", (project_id,)).fetchall()
    return [{"id": r[0], "query": r[1], "purpose": r[2], "channel": r[3],
             "hits": len(json.loads(r[4])), "at": r[5]} for r in rows]


def sources(store: Store, project_id: int, with_content: bool = False) -> list[dict[str, Any]]:
    cols = "id, url, domain, title, sha256, truncated, fetched_at" + (
        ", content" if with_content else "")
    with store.tx() as conn:
        rows = conn.execute(f"SELECT {cols} FROM sources WHERE project_id = ? ORDER BY id",
                            (project_id,)).fetchall()
    out = []
    for r in rows:
        item = {"id": r[0], "url": r[1], "domain": r[2], "title": r[3], "sha256": r[4],
                "truncated": bool(r[5]), "fetched_at": r[6]}
        if with_content:
            item["content"] = r[7]
        out.append(item)
    return out


def get_source(store: Store, project_id: int, ref: Any) -> dict[str, Any]:
    sid = parse_ref(ref, "S")
    for src in sources(store, project_id, with_content=True):
        if src["id"] == sid:
            return src
    raise ToolError(f"no source S{sid} in this project; fetch the page first")


def claims(store: Store, project_id: int, active_only: bool = False) -> list[dict[str, Any]]:
    sql = ("SELECT id, text, type, label, evidence, as_of, status, note, created_at, updated_at"
           " FROM claims WHERE project_id = ?")
    if active_only:
        sql += " AND status = 'active'"
    with store.tx() as conn:
        rows = conn.execute(sql + " ORDER BY id", (project_id,)).fetchall()
    return [{"id": r[0], "text": r[1], "type": r[2], "label": r[3],
             "evidence": json.loads(r[4]), "as_of": r[5], "status": r[6], "note": r[7],
             "created_at": r[8], "updated_at": r[9]} for r in rows]


def get_claim(store: Store, project_id: int, ref: Any) -> dict[str, Any]:
    cid = parse_ref(ref, "C")
    for c in claims(store, project_id):
        if c["id"] == cid:
            return c
    raise ToolError(f"no claim C{cid} in this project")


def update_claim(store: Store, claim_id: int, **fields: Any) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    with store.tx() as conn:
        conn.execute(f"UPDATE claims SET {sets}, updated_at = ? WHERE id = ?",
                     (*fields.values(), store.now(), claim_id))


def claim_tag(c: dict[str, Any]) -> str:
    if c["status"] != "active":
        return "retracted"
    return evidence.LABELS.get(c["label"], c["label"])


def _date(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


# the tool ------------------------------------------------------------------------------------

class ResearchTool(BoundTool):
    def __init__(self, store_factory: Callable[[], Store], dispatch: Dispatch,
                 runner: Runner) -> None:
        super().__init__(store_factory)
        self._dispatch = dispatch
        self._runner = runner

    def _call(self, name: str, payload: dict) -> Any:
        raw = self._dispatch(name, payload)
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            raise ToolError(f"{name} returned non-JSON: {str(raw)[:300]}") from None

    @staticmethod
    def _open(project: Project, what: str) -> None:
        require_phase(project, 2, 3, 4, 5, 6, what=what)

    # plan / search / fetch / read -------------------------------------------------------------

    def act_plan(self, store: Store, project: Project, args: dict) -> dict:
        require_phase(project, 2, what="the research plan")
        tier = args.get("tier") or "standard"
        if tier not in TIERS:
            raise ToolError(f"tier must be one of {', '.join(TIERS)}")
        kind = args.get("kind") or "software"
        questions = [q.strip() for q in args.get("questions") or [] if str(q).strip()]
        if len(questions) < 3:
            raise ToolError("a research plan needs at least 3 questions (user/demand, "
                            "competitors, feasibility, distribution)")
        plan = {"tier": tier, "kind": kind, "questions": questions}
        store.add_artifact(project.id, project.phase, "research_plan", PRODUCER, plan)
        return {"plan": plan, "requirements": self._requirements(plan)}

    @staticmethod
    def _requirements(plan: dict) -> dict:
        tier = TIERS[plan["tier"]]
        channels = list(tier["channels"]) if plan.get("kind") == "software" else ["web"]
        return {"min_claims": tier["min_claims"], "min_verified": 1,
                "min_disconfirm_searches": tier["min_disconfirm"],
                "competitor_channels": channels, "verifier": "must run after the last claim"}

    def act_search(self, store: Store, project: Project, args: dict) -> dict:
        self._open(project, "research")
        query = str(args.get("query") or "").strip()
        purpose = args.get("purpose") or "support"
        channel = args.get("channel") or ""
        if not query:
            raise ToolError("search needs a query")
        if purpose not in PURPOSES:
            raise ToolError(f"purpose must be one of {', '.join(PURPOSES)}")
        if purpose == "competitor" and channel not in CHANNELS:
            raise ToolError(f"competitor searches name a channel: {', '.join(CHANNELS)}")
        data = self._call("web_search", {"query": query, "limit": 8})
        hits = ((data.get("data") or {}).get("web") or []) if isinstance(data, dict) else []
        results = [{"title": h.get("title", ""), "url": h.get("url", ""),
                    "snippet": (h.get("description") or "")[:400]} for h in hits]
        with store.tx() as conn:
            cur = conn.execute(
                "INSERT INTO searches (project_id, query, purpose, channel, results, at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (project.id, query, purpose, channel,
                 json.dumps(results, ensure_ascii=False), store.now()))
        reply = {"search": cur.lastrowid, "results": results,
                 "note": "Snippets are leads. Fetch a page before you claim anything from it."}
        if not results:
            reply["note"] = ("No results. If this was a check that something exists, keep the "
                             "search id for an absence claim.")
            if isinstance(data, dict) and data.get("error"):
                reply["backend_error"] = str(data["error"])[:300]
        return reply

    def act_fetch(self, store: Store, project: Project, args: dict) -> dict:
        self._open(project, "research")
        urls = [str(u).strip() for u in args.get("urls") or [] if str(u).strip()][:5]
        if not urls:
            raise ToolError("fetch needs urls (up to 5)")
        data = self._call("web_extract", {"urls": urls, "char_limit": FETCH_CHAR_LIMIT})
        pages = (data.get("results") or []) if isinstance(data, dict) else []
        if not pages:
            problem = data.get("error") if isinstance(data, dict) else None
            raise ToolError("web_extract returned no pages"
                            + (f": {str(problem)[:300]}" if problem else ""),
                            hint="check that the web toolset is enabled, or try other urls")
        out = []
        for page in pages:
            url = page.get("url") or ""
            content = page.get("content") or ""
            if page.get("error") or not content.strip():
                out.append({"url": url, "error": page.get("error") or "empty page"})
                continue
            digest = evidence.content_hash(content)
            truncated = "[TRUNCATED]" in content
            with store.tx() as conn:
                row = conn.execute("SELECT id FROM sources WHERE project_id = ? AND url = ?"
                                   " AND sha256 = ?", (project.id, url, digest)).fetchone()
                if row:
                    sid = row[0]
                else:
                    sid = conn.execute(
                        "INSERT INTO sources (project_id, url, domain, title, content, sha256,"
                        " truncated, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (project.id, url, evidence.domain_of(url), page.get("title") or "",
                         content, digest, int(truncated), store.now())).lastrowid
            out.append({"source": f"S{sid}", "url": url, "title": page.get("title") or "",
                        "chars": len(content), "truncated": truncated,
                        "text": content[:RETURN_CHARS],
                        "more": max(0, len(content) - RETURN_CHARS)})
        return {"pages": out,
                "note": "Quote exact words from 'text' in claims. Use read with find/offset "
                        "for the rest of a long page."}

    def act_read(self, store: Store, project: Project, args: dict) -> dict:
        src = get_source(store, project.id, args.get("source"))
        content = src["content"]
        if args.get("find"):
            return {"source": f"S{src['id']}", "url": src["url"],
                    "matches": evidence.find_snippets(content, str(args["find"]))}
        offset = max(0, int(args.get("offset") or 0))
        return {"source": f"S{src['id']}", "url": src["url"], "offset": offset,
                "text": content[offset:offset + RETURN_CHARS],
                "more": max(0, len(content) - offset - RETURN_CHARS)}

    # claims ------------------------------------------------------------------------------------

    def act_claim(self, store: Store, project: Project, args: dict) -> dict:
        self._open(project, "claims")
        text = str(args.get("text") or "").strip()
        ctype = args.get("type") or "other"
        if not text:
            raise ToolError("claim needs text (one atomic, checkable statement)")
        if ctype == "competitor_absent":
            raise ToolError("use action=absence for nothing-exists claims")
        contested = bool(args.get("contested"))
        items = args.get("evidence") or []
        if args.get("unverified"):
            if items:
                raise ToolError("unverified claims carry no evidence; drop one or the other")
            label, checked = "unverified", []
        else:
            if not items:
                raise ToolError("a claim needs evidence [{source: S#, quote}] from fetched "
                                "pages, or unverified=true to log it as a 🔍 lead")
            checked, failures = [], []
            for item in items:
                src = get_source(store, project.id, item.get("source"))
                quote = str(item.get("quote") or "").strip()
                if evidence.quote_in(quote, src["content"]):
                    checked.append({"source": src["id"], "quote": quote, "url": src["url"],
                                    "domain": src["domain"], "sha256": src["sha256"]})
                else:
                    why = ("too short (at least 20 characters)"
                           if len(evidence.normalize(quote)) < evidence.MIN_QUOTE_CHARS
                           else "not found in the page text")
                    failures.append({"source": f"S{src['id']}", "quote": quote[:120],
                                     "problem": why})
            if failures:
                raise ToolError("quote check failed; copy the exact words from the page "
                                "(read with find helps)", failures=failures)
            independent = evidence.independent_count(
                [(c["domain"], c["sha256"]) for c in checked])
            label = evidence.label_for(ctype, contested, independent)
        as_of = str(args.get("as_of") or "") or (
            _date(store.now()) if checked else "")
        now = store.now()
        with store.tx() as conn:
            cid = conn.execute(
                "INSERT INTO claims (project_id, text, type, label, evidence, as_of, status,"
                " note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)",
                (project.id, text, ctype, label, json.dumps(checked, ensure_ascii=False),
                 as_of, "contested" if contested else "", now, now)).lastrowid
        need = evidence.required_sources(ctype, contested)
        reply = {"claim": f"C{cid}", "label": evidence.LABELS[label], "as_of": as_of}
        if label == "partial":
            reply["note"] = (f"{ctype}{' (contested)' if contested else ''} needs {need} "
                             "independent sources (different sites, not a republished copy) "
                             "for ✅.")
        return reply

    def act_absence(self, store: Store, project: Project, args: dict) -> dict:
        self._open(project, "claims")
        text = str(args.get("text") or "").strip()
        ids = sorted({int(i) for i in args.get("searches") or []})
        if not text:
            raise ToolError("absence needs text, e.g. 'No Hermes plugin does X'")
        known = {s["id"]: s for s in searches(store, project.id)}
        missing_ids = [i for i in ids if i not in known]
        if missing_ids:
            raise ToolError(f"unknown search ids: {missing_ids}")
        if len(ids) < 3:
            raise ToolError("an absence claim needs at least 3 logged searches behind it "
                            "(different channels or phrasings)")
        where = [{"search": i, "query": known[i]["query"],
                  "channel": known[i]["channel"] or known[i]["purpose"]} for i in ids]
        now = store.now()
        with store.tx() as conn:
            cid = conn.execute(
                "INSERT INTO claims (project_id, text, type, label, evidence, as_of, status,"
                " note, created_at, updated_at) VALUES (?, ?, 'competitor_absent', 'absent', ?,"
                " ?, 'active', '', ?, ?)",
                (project.id, text, json.dumps(where, ensure_ascii=False), _date(now), now,
                 now)).lastrowid
        return {"claim": f"C{cid}", "label": evidence.LABELS["absent"],
                "note": "Absence is never ✅: the briefing lists where we looked."}

    def act_retract(self, store: Store, project: Project, args: dict) -> dict:
        claim = get_claim(store, project.id, args.get("claim"))
        reason = str(args.get("reason") or "").strip()
        if not reason:
            raise ToolError("retract needs a reason (it is shown in the briefing)")
        update_claim(store, claim["id"], status="retracted", note=reason)
        return {"claim": f"C{claim['id']}", "status": "retracted"}

    # verifier ----------------------------------------------------------------------------------

    def act_verify(self, store: Store, project: Project, args: dict) -> dict:
        self._open(project, "verification")
        active = [c for c in claims(store, project.id, active_only=True)
                  if c["label"] in ("verified", "partial")]
        if not active:
            raise ToolError("nothing to verify: record claims with evidence first")
        job = Job(role="verifier", project_id=project.id, goal=VERIFIER_GOAL,
                  context=verifier_packet(store, project, active), toolsets=("web",))
        outcome = self._runner(job)
        started = store.now()
        if not outcome.ok:
            payload = {"status": "skipped", "reason": outcome.error, "claims": len(active),
                       "at": started}
            store.add_artifact(project.id, project.phase, "verification", PRODUCER, payload)
            return {"verification": "skipped", "reason": outcome.error,
                    "note": "The briefing will say the independent verifier did not run."}
        try:
            verdicts = parse_verifier(outcome.text)
        except ValueError as exc:
            payload = {"status": "skipped", "reason": f"unreadable verifier reply: {exc}",
                       "claims": len(active), "at": started}
            store.add_artifact(project.id, project.phase, "verification", PRODUCER, payload)
            return {"verification": "skipped", "reason": payload["reason"]}
        by_id = {c["id"]: c for c in active}
        changes = []
        for v in verdicts:
            claim = by_id.get(v["id"])
            if claim is None:
                continue
            if v["verdict"] == "unsupported":
                update_claim(store, claim["id"], status="retracted",
                             note=f"verifier: {v['note'] or 'quote does not support the claim'}")
                changes.append({"claim": f"C{claim['id']}", "now": "retracted",
                                "why": v["note"]})
            elif v["verdict"] == "partial" or (
                    claim["label"] == "verified" and not v["original"]):
                if claim["label"] == "verified":
                    why = v["note"] or ("copy of another source" if not v["original"]
                                        else "only partly supported")
                    update_claim(store, claim["id"], label="partial",
                                 note=f"verifier: {why}")
                    changes.append({"claim": f"C{claim['id']}", "now": "⚠️", "why": why})
        payload = {"status": "ok", "model": outcome.model, "claims": len(active),
                   "checked": len(verdicts), "changes": changes, "at": started}
        store.add_artifact(project.id, project.phase, "verification", PRODUCER, payload)
        return {"verification": "ok", "model": outcome.model, "checked": len(verdicts),
                "changes": changes}

    # briefing ----------------------------------------------------------------------------------

    def act_briefing(self, store: Store, project: Project, args: dict) -> dict:
        require_phase(project, 2, what="the briefing")
        summary = str(args.get("summary") or "").strip()
        if not summary:
            raise ToolError("briefing needs a summary that cites claims inline as [C#]")
        plan = research_plan(store, project)
        req = self._requirements(plan)
        all_claims = claims(store, project.id)
        active = [c for c in all_claims if c["status"] == "active"]
        problems: list[str] = []
        cited = {int(n) for n in re.findall(r"\[C(\d+)\]", summary)}
        known = {c["id"]: c for c in all_claims}
        if not cited:
            problems.append("the summary cites no claim; reference claims inline as [C#]")
        bad = sorted(n for n in cited if n not in known)
        if bad:
            problems.append(f"the summary cites unknown claims: {', '.join(f'C{n}' for n in bad)}")
        gone = sorted(n for n in cited if n in known and known[n]["status"] != "active")
        if gone:
            problems.append("the summary cites retracted claims: "
                            + ", ".join(f"C{n}" for n in gone))
        if len(active) < req["min_claims"]:
            problems.append(f"{len(active)} claims; tier {plan['tier']} needs "
                            f"{req['min_claims']}")
        if not any(c["label"] == "verified" for c in active):
            problems.append("no ✅ claim yet: fetch a primary page and quote it")
        log = searches(store, project.id)
        disconfirm = [s for s in log if s["purpose"] == "disconfirm"]
        if len(disconfirm) < req["min_disconfirm_searches"]:
            problems.append(f"{len(disconfirm)} disconfirmation searches; need "
                            f"{req['min_disconfirm_searches']} ('X failed', 'why not X', "
                            "'X alternatives', 'X criticism')")
        swept = {s["channel"] for s in log if s["purpose"] == "competitor"}
        if plan.get("kind") != "software":
            swept |= {"web"} if log else set()
        unswept = [ch for ch in req["competitor_channels"] if ch not in swept]
        if unswept:
            problems.append("competitor sweep missing channels: " + ", ".join(unswept))
        verification = store.latest(project.id, "verification")
        newest = max((c["created_at"] for c in active), default=0)
        if verification is None or verification.payload.get("at", 0) < newest:
            problems.append("run action=verify after the last claim")
        if problems:
            raise ToolError("the briefing is not ready", problems=problems,
                            requirements=req)
        markdown = render_briefing(store, project, summary, args, plan, verification.payload)
        stats = {"claims": len(active),
                 "verified": sum(c["label"] == "verified" for c in active),
                 "searches": len(log), "sources": len(sources(store, project.id)),
                 "verifier": verification.payload.get("status")}
        art = store.add_artifact(project.id, project.phase, "briefing", PRODUCER,
                                 {"markdown": markdown, "stats": stats})
        return {"briefing": art.id, "stats": stats, "markdown": markdown,
                "next": "Show the briefing to the user, then idea_phase(action=advance)."}

    def act_ledger(self, store: Store, project: Project, args: dict) -> dict:
        return {"claims": [{"id": f"C{c['id']}", "tag": claim_tag(c), "type": c["type"],
                            "text": c["text"], "note": c["note"]}
                           for c in claims(store, project.id)],
                "sources": [{"id": f"S{s['id']}", "url": s["url"], "title": s["title"]}
                            for s in sources(store, project.id)],
                "searches": searches(store, project.id),
                "plan": research_plan(store, project)}


# verifier packet and reply -------------------------------------------------------------------

VERIFIER_GOAL = """You are an independent fact verifier. You did not write these claims and you
have no stake in them. For each claim, judge whether the quoted source text really supports the
claim as worded (not a broader or stronger version of it), and whether the source is the original
(the vendor, the paper, the official page, the repo) rather than a copy or a write-up of another
page. You may fetch the URLs to check context or look for the original.

Reply with JSON only, no prose:
{"claims": [{"id": "C1", "verdict": "supported" | "partial" | "unsupported",
             "original": true | false, "note": "one short sentence"}]}
Use "partial" when the quote supports only part of the claim or the claim overstates it."""


def verifier_packet(store: Store, project: Project, active: list[dict]) -> str:
    content = {s["id"]: s["content"] for s in sources(store, project.id, with_content=True)}
    lines = [f"Project idea (for context only): {project.idea}", "", "Claims:"]
    for c in active:
        lines.append(f"\n{c['id'] and 'C' + str(c['id'])} [{c['type']}] {c['text']}")
        for ev in c["evidence"]:
            page = content.get(ev["source"], "")
            lines.append(f"  source S{ev['source']} {ev['url']}")
            lines.append(f"  quote: \"{ev['quote']}\"")
            window = _window(page, ev["quote"])
            if window:
                lines.append(f"  around the quote: \"{window}\"")
    return "\n".join(lines)


def _window(page: str, quote: str, width: int = 400) -> str:
    probe = quote.strip()[:40]
    found = evidence.find_snippets(page, probe, width=width, limit=1) if probe else []
    return found[0].replace("\n", " ") if found else ""


def parse_verifier(text: str) -> list[dict[str, Any]]:
    data = extract_json(text)
    items = data.get("claims") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("expected a 'claims' list")
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            cid = parse_ref(item.get("id"), "C")
        except ToolError:
            continue
        verdict = str(item.get("verdict") or "").lower()
        if verdict not in ("supported", "partial", "unsupported"):
            continue
        out.append({"id": cid, "verdict": verdict,
                    "original": item.get("original") is not False,
                    "note": str(item.get("note") or "")[:300]})
    if not out:
        raise ValueError("no usable verdicts")
    return out


# briefing rendering --------------------------------------------------------------------------

def render_briefing(store: Store, project: Project, summary: str, args: dict, plan: dict,
                    verification: dict) -> str:
    all_claims = claims(store, project.id)
    srcs = {s["id"]: s for s in sources(store, project.id)}
    log = searches(store, project.id)
    out = [f"# Context briefing: {project.title}", "", summary.strip(), ""]
    for title, key in (("Surprises", "surprises"), ("Unknowns", "unknowns")):
        items = [str(x).strip() for x in args.get(key) or [] if str(x).strip()]
        if items:
            out += [f"## {title}", ""] + [f"- {x}" for x in items] + [""]
    out += ["## Claims", ""]
    for c in all_claims:
        meta = [", ".join(f"S{e['source']}" for e in c["evidence"] if "source" in e)]
        meta.append(f"as of {c['as_of']}" if c["as_of"] else "")
        meta_text = "; ".join(m for m in meta if m)
        out.append(f"- C{c['id']} {claim_tag(c)} {c['text']}"
                   + (f" ({meta_text})" if meta_text else ""))
    out += ["", "## Source log", "",
            "| S# | Page | Fetched | Used by |", "|---|---|---|---|"]
    used: dict[int, list[str]] = {}
    for c in all_claims:
        for e in c["evidence"]:
            if "source" in e:
                ids = used.setdefault(e["source"], [])
                if f"C{c['id']}" not in ids:  # a claim may quote one page twice
                    ids.append(f"C{c['id']}")
    for sid, s in srcs.items():
        title = (s["title"] or s["url"]).replace("|", "/")[:80]
        out.append(f"| S{sid} | [{title}]({s['url']}) | {_date(s['fetched_at'])} | "
                   f"{', '.join(used.get(sid, [])) or '-'} |")
    by_purpose: dict[str, int] = {}
    for s in log:
        by_purpose[s["purpose"]] = by_purpose.get(s["purpose"], 0) + 1
    channels = sorted({s["channel"] for s in log if s["channel"]})
    tail = 0
    created = sorted(c["created_at"] for c in all_claims)
    for s in reversed(log):
        if any(t > s["at"] for t in created):
            break
        tail += 1
    out += ["", "## Coverage", "",
            f"- Tier: {plan['tier']}. {len(log)} searches ("
            + ", ".join(f"{k} {v}" for k, v in sorted(by_purpose.items())) + f"), "
            f"{len(srcs)} pages fetched, {len(all_claims)} claims.",
            f"- Competitor channels checked: {', '.join(channels) or 'none'}.",
            f"- Searches at the end that added no claim: {tail}."]
    if verification.get("status") == "ok":
        out.append(f"- Independent verifier ({verification.get('model')}): "
                   f"{verification.get('checked')} claims checked, "
                   f"{len(verification.get('changes') or [])} changed.")
    not_verified = [c for c in all_claims
                    if c["status"] != "active" or c["label"] != "verified"]
    out += ["", "## Not verified", ""]
    if verification.get("status") != "ok":
        out.append(f"- The independent verifier did not run ({verification.get('reason')}).")
    for c in not_verified:
        if c["status"] != "active":
            out.append(f"- C{c['id']} retracted: {c['text']} ({c['note']})")
        elif c["label"] == "absent":
            where = "; ".join(f"{w['channel']}: \"{w['query']}\"" for w in c["evidence"])
            out.append(f"- C{c['id']} absence, not provable: {c['text'].rstrip('.')}. "
                       f"Looked in: {where}")
        else:
            out.append(f"- C{c['id']} {claim_tag(c)} {c['text']}"
                       + (f" ({c['note']})" if c["note"] else ""))
    if len(out) and out[-1] == "":
        out.pop()
    return "\n".join(out).strip() + "\n"

