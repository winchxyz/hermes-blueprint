"""Dated base rates the planner and the critic must start from (outside view first).

Unit classes: agent-bound active hours per work unit, from the owner's velocity ledger
(docs/research/estimation.md 3.2). Reference classes: outcome distributions with their sources
(docs/research/research-and-judgment.md B5). Each row carries its source and an as-of date and
should be reviewed every quarter: agent time horizons double every few months.
"""
from __future__ import annotations

from typing import Any

REVIEWED = "2026-11"

# key -> (description, P10, P50, P90 active hours, basis)
UNIT_CLASSES: dict[str, tuple[str, float, float, float, str]] = {
    "scaffold": ("Scaffold, single-file tool, static page, plugin skeleton",
                 0.3, 1.0, 3.0, "velocity ledger: drawing site, voxel game, plugin build"),
    "api_integration": ("Integration with one documented external API, with tests",
                        0.5, 1.5, 4.0, "velocity ledger: plugin build"),
    "polished_feature": ("Polished web toy or app feature with custom rendering",
                         1.0, 3.0, 8.0, "velocity ledger: 3 web apps"),
    "core_engine": ("Game or app with physics, rendering or a solver core",
                    5.0, 12.0, 30.0, "velocity ledger: 3 games and apps"),
    "multi_component": ("Multi-component product slice (backend + frontend + deploy)",
                        10.0, 30.0, 80.0, "velocity ledger: 2 products"),
    "money_code": ("Contracts or real-money code (excluding audits)",
                   10.0, 40.0, 100.0, "velocity ledger: 2 contract apps"),
    "promo_video": ("Promo video or reel with an existing pipeline",
                    1.0, 2.0, 6.0, "velocity ledger: 3 videos"),
    "docs": ("README, docs, catalog or store listing text",
             0.3, 1.0, 2.5, "velocity ledger: plugin catalog assets"),
}

MULTIPLIERS = {
    "unfamiliar_toolchain": (1.5, 3.0, "game engines, modloaders, native mobile"),
    "unseen_codebase": (2.0, 4.0, "large existing codebase the agent has not seen"),
    "novel_problem": (2.0, 5.0, "novel algorithm or research question; widen P90"),
}

# key -> facts the critic can cite as an outside view.
REFERENCE_CLASSES: dict[str, dict[str, Any]] = {
    "steam_games": {
        "name": "Steam games released in 2025",
        "rate": "about 20,000 releases; median revenue about $249; about 66% earned under "
                "$1,000 (estimates may be off by up to ~50%)",
        "source": "https://gamedevreport.beehiiv.com/p/19-606-steam-games-made-16b-in-2025-"
                  "most-made-0-but-that-s-not-a-problem",
        "as_of": "2026-01", "confidence": "secondary"},
    "chrome_extensions": {
        "name": "Chrome Web Store extensions (2019 snapshot)",
        "rate": "87% under 1,000 installs; 50% under 16 installs; about 10% with zero",
        "source": "https://www.techspot.com/news/81286-most-google-chrome-extensions-have-"
                  "fewer-than-1000.html",
        "as_of": "2019-06", "confidence": "secondary, dated"},
    "us_new_businesses": {
        "name": "US new employer establishments",
        "rate": "about 49% survive 5 years (1994-2022 average); a poor class for side projects",
        "source": "https://www.bls.gov/bdm/bdagefaq.htm",
        "as_of": "2023", "confidence": "secondary"},
    "ai_dev_speed_belief": {
        "name": "Experienced developers using AI tools on their own repos (early 2025)",
        "rate": "19% slower, after expecting 24% faster, and still believed afterwards they "
                "had been 20% faster",
        "source": "https://arxiv.org/abs/2507.09089",
        "as_of": "2025-07", "confidence": "primary"},
    "agent_task_horizon": {
        "name": "AI agent task length (50% time horizon)",
        "rate": "about 50 minutes for Claude 3.7 Sonnet; doubling roughly every 7 months "
                "since 2019",
        "source": "https://arxiv.org/abs/2503.14499",
        "as_of": "2025-03", "confidence": "primary"},
}

# Calendar-bound waits (W items) a solo builder hits; official pages, see research B6.
WAIT_CATALOG: dict[str, str] = {
    "google_play_new_account": "12 testers opted in for 14 consecutive days before production",
    "apple_review": "50% of submissions reviewed in <24 h, 90% in <48 h",
    "steam_release": "$100 fee, 21-day wait after paying, Coming Soon page live >= 2 weeks",
    "chrome_web_store": "most reviews within a few days, up to a few weeks",
    "plugin_catalog_review": "maintainer review of a catalog PR: days, not in your control",
}


def unit_class_table() -> list[dict[str, Any]]:
    return [{"class": k, "what": v[0], "p10_h": v[1], "p50_h": v[2], "p90_h": v[3],
             "basis": v[4]} for k, v in UNIT_CLASSES.items()]


def reference_class_table() -> list[dict[str, Any]]:
    return [{"key": k, **v} for k, v in REFERENCE_CLASSES.items()]
