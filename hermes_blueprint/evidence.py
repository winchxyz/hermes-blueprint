"""Evidence rules that code checks, so a ✅ cannot come from a search snippet or a memory.

- A quote counts only if it appears in the stored text of a page the plugin fetched itself,
  after folding case, whitespace, markup and typographic quotes and dashes.
- Independence: two sources count twice only if they come from different sites and their text
  is not the same page republished.
- Each claim type has a minimum number of independent sources for ✅. Absence claims ("nothing
  like this exists") are never ✅: they record where we looked.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlparse

_FOLD = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "´": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "«": '"', "»": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
    "−": "-",
})
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MARKUP = re.compile(r"[*_`#>|~]+|\\(?=[^\w\s])")
_SPACE = re.compile(r"\s+")
_DASH_SPACING = re.compile(r"\s*-\s*")

MIN_QUOTE_CHARS = 20

# Independent sources needed for ✅, by claim type. None = never ✅ (absence claims).
CLAIM_TYPES: dict[str, int | None] = {
    "market_size": 2,        # numbers about a market or audience
    "traction": 2,           # downloads, revenue, users of someone else's product
    "price": 1,              # the vendor's own pricing page is the primary source
    "competitor_exists": 1,  # the product's own page or repo
    "technical": 1,          # official docs, the repo, the spec
    "policy": 1,             # the official policy or regulation page
    "other": 1,
    "competitor_absent": None,
}
CONTESTED_MIN = 2

LABELS = {"verified": "✅", "partial": "⚠️", "unverified": "🔍", "absent": "🔍 absence"}

_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu", "ne", "or"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").translate(_FOLD)
    text = _LINK.sub(r"\1", text)
    text = _MARKUP.sub(" ", text).casefold()
    text = _SPACE.sub(" ", text)
    return _DASH_SPACING.sub("-", text).strip()


def quote_in(quote: str, content: str) -> bool:
    q = normalize(quote).strip(" .\"'")
    return len(q) >= MIN_QUOTE_CHARS and q in normalize(content)


def find_snippets(content: str, phrase: str, width: int = 300, limit: int = 5) -> list[str]:
    """Raw-text windows around case-insensitive matches of ``phrase`` (for reading a source)."""
    out: list[str] = []
    if not phrase.strip():
        return out
    for m in re.finditer(re.escape(phrase.strip()), content, re.I):
        lo, hi = max(0, m.start() - width), min(len(content), m.end() + width)
        out.append(("…" if lo else "") + content[lo:hi] + ("…" if hi < len(content) else ""))
        if len(out) >= limit:
            break
    return out


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in _SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def content_hash(content: str) -> str:
    return hashlib.sha256(normalize(content).encode("utf-8")).hexdigest()


def independent_count(sources: list[tuple[str, str]]) -> int:
    """Number of independent sources among ``(domain, sha256)`` pairs: one per site, and a page
    republished word for word on another site does not count again."""
    domains: set[str] = set()
    hashes: set[str] = set()
    count = 0
    for domain, digest in sources:
        if domain in domains or digest in hashes:
            continue
        domains.add(domain)
        hashes.add(digest)
        count += 1
    return count


def required_sources(claim_type: str, contested: bool) -> int | None:
    if claim_type not in CLAIM_TYPES:
        raise ValueError(f"claim type must be one of {', '.join(CLAIM_TYPES)}")
    need = CLAIM_TYPES[claim_type]
    if need is None:
        return None
    return max(need, CONTESTED_MIN) if contested else need


def label_for(claim_type: str, contested: bool, independent: int) -> str:
    need = required_sources(claim_type, contested)
    if need is None:
        return "absent"
    if independent >= need:
        return "verified"
    return "partial" if independent else "unverified"
