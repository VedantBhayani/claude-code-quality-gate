"""fresh_per_company: one freshest sales-ish post per company inside a freshness window.

Used for a "who to email this week" sample: every company counts once, its signal is
the newest sales-ish post, and a core sales role beats an ambiguous one.
"""
from datetime import date, timedelta

import pytest

from quality_gate.config import load_config
from quality_gate.sampler import fresh_per_company
from quality_gate.types import Post

COLLECTED = date(2026, 10, 22)


def _post(pid: str, company: str, title: str, days_old: int, domain: str | None = None) -> Post:
    return Post(
        post_id=pid, company=company, domain=domain if domain is not None else f"{company.lower()}.com",
        title=title, url=f"https://boards.example/{pid}", post_date=COLLECTED - timedelta(days=days_old),
        collection_date=COLLECTED, ats="greenhouse", text="...",
    )


@pytest.fixture
def rules(package_root):
    return load_config(package_root).title_filter()


def ids(posts):
    return [p.post_id for p in posts]


def test_keeps_the_freshest_sales_post_per_company(rules):
    posts = [
        _post("a-old", "Acme", "Account Executive", 10),
        _post("a-new", "Acme", "SDR", 2),
        _post("b-1", "Beta", "Head of Sales", 5),
    ]
    natural, ambiguous = fresh_per_company(posts, rules, window_days=14)
    assert ids(natural) == ["a-new", "b-1"]
    assert ambiguous == []


def test_a_core_sales_role_beats_a_fresher_ambiguous_one(rules):
    posts = [
        _post("a-amb", "Acme", "Customer Success Manager", 1),
        _post("a-core", "Acme", "Account Executive", 9),
    ]
    natural, ambiguous = fresh_per_company(posts, rules, window_days=14)
    assert ids(natural) == ["a-core"]
    assert ambiguous == []


def test_a_company_with_only_ambiguous_fresh_posts_goes_to_the_ambiguous_list(rules):
    posts = [_post("c-amb", "Gamma", "Solutions Engineer", 3), _post("c-old", "Gamma", "Account Executive", 40)]
    natural, ambiguous = fresh_per_company(posts, rules, window_days=14)
    assert natural == []
    assert ids(ambiguous) == ["c-amb"]


@pytest.mark.parametrize("days_old, kept", [(0, True), (14, True), (15, False), (-1, False)])
def test_window_edges_and_future_dated_posts(rules, days_old, kept):
    natural, _ = fresh_per_company([_post("p", "Acme", "Account Executive", days_old)], rules, window_days=14)
    assert (ids(natural) == ["p"]) is kept


def test_non_sales_titles_never_count(rules):
    natural, ambiguous = fresh_per_company([_post("x", "Acme", "Software Engineer", 1)], rules, window_days=14)
    assert natural == [] and ambiguous == []


def test_companies_are_keyed_by_domain_and_ties_break_on_post_id(rules):
    posts = [
        _post("z", "Acme Inc", "Account Executive", 3, domain="acme.com"),
        _post("y", "Acme", "SDR", 3, domain="acme.com"),
    ]
    natural, _ = fresh_per_company(posts, rules, window_days=14)
    assert ids(natural) == ["y"]


def test_result_order_does_not_depend_on_input_order(rules):
    posts = [_post(f"p{i}", f"Co{i}", "Account Executive", i % 5) for i in range(12)]
    first, _ = fresh_per_company(posts, rules, window_days=14)
    second, _ = fresh_per_company(list(reversed(posts)), rules, window_days=14)
    assert ids(first) == ids(second) == sorted(ids(first))
