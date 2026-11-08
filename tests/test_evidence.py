"""Quote checks, independence and labels: the rules behind every ✅."""
from __future__ import annotations

import pytest

from hermes_blueprint import evidence


def test_quote_survives_typography_markup_and_case():
    page = "The fee is **$100** — “recoupable” after [$1,000 AGR](https://x)."
    assert evidence.quote_in('The fee is $100 - "recoupable" after $1,000 AGR', page)
    assert evidence.quote_in("THE FEE IS $100 – ‘recoupable’", page.replace(
        "“", "‘").replace("”", "’"))


def test_quote_must_be_long_enough_and_present():
    page = "Most clubs still take bookings by phone or WhatsApp."
    assert not evidence.quote_in("by phone", page)
    assert not evidence.quote_in("Most clubs take bookings online", page)
    assert evidence.quote_in("most clubs still take bookings by phone", page)


@pytest.mark.parametrize("url,domain", [
    ("https://www.example.com/a", "example.com"),
    ("https://docs.example.com/a", "example.com"),
    ("https://news.bbc.co.uk/x", "bbc.co.uk"),
    ("http://localhost:8000/x", "localhost"),
])
def test_domain_of(url, domain):
    assert evidence.domain_of(url) == domain


def test_independence_counts_sites_and_ignores_copies():
    a = evidence.content_hash("Original report text")
    b = evidence.content_hash("A different article")
    assert evidence.independent_count([("a.com", a), ("b.org", b)]) == 2
    assert evidence.independent_count([("a.com", a), ("a.com", b)]) == 1
    assert evidence.independent_count([("a.com", a), ("mirror.net", a)]) == 1


def test_labels_by_type():
    assert evidence.label_for("price", False, 1) == "verified"
    assert evidence.label_for("market_size", False, 1) == "partial"
    assert evidence.label_for("market_size", False, 2) == "verified"
    assert evidence.label_for("technical", True, 1) == "partial"
    assert evidence.label_for("competitor_absent", False, 9) == "absent"
    with pytest.raises(ValueError):
        evidence.required_sources("vibes", False)


def test_find_snippets():
    text = "alpha beta GAMMA delta " * 3
    hits = evidence.find_snippets(text, "gamma", width=5)
    assert len(hits) == 3 and "GAMMA" in hits[0]
