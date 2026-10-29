from dataclasses import replace

from gift_fixtures import make_post, make_run, no, passing_checks, yes

from quality_gate.gift.select import GIFT_FIELDS, select_gift


def _ids(rows):
    return [r.post_id for r in rows]


def test_only_hand_labelled_signals_inside_the_window_qualify(rules):
    posts = [
        make_post("p1", "Acme", 3),
        make_post("p2", "Beta", 3),  # hand label says not a signal
        make_post("p3", "Gamma", 14),  # on the edge: still in
        make_post("p4", "Delta", 15),  # outside the window
        make_post("p5", "Epsilon", -1),  # dated after collection: never fresh
        make_post("p6", "Zeta", 2),  # no hand label at all
    ]
    labels = [yes("p1"), no("p2"), yes("p3"), yes("p4"), yes("p5")]
    runs = [make_run(p.post_id, 40) for p in posts]
    rows = select_gift(posts, labels, runs, {}, rules)
    assert sorted(_ids(rows)) == ["p1", "p3"]


def test_one_row_per_company_keeping_its_freshest_qualifying_post(rules):
    posts = [make_post("old", "Acme", 10), make_post("new", "Acme", 2), make_post("stale", "Acme", 20)]
    labels = [yes("old"), yes("new"), yes("stale")]
    runs = [make_run("old", 48), make_run("new", 30), make_run("stale", 50)]
    rows = select_gift(posts, labels, runs, {}, rules)
    assert _ids(rows) == ["new"]


def test_ranked_by_sonnet_run_one_score_ties_broken_by_recency(rules):
    posts = [make_post("a", "A", 9), make_post("b", "B", 4), make_post("c", "C", 1)]
    labels = [yes("a"), yes("b"), yes("c")]
    runs = [
        make_run("a", 44),
        make_run("b", 37),
        make_run("c", 37),
        # Other arms and repeats never drive the ranking.
        make_run("b", 50, arm="haiku-5-5", model="claude-haiku-5-5"),
        make_run("c", 10, repeat=2),
    ]
    rows = select_gift(posts, labels, runs, {}, rules)
    assert _ids(rows) == ["a", "c", "b"]
    assert [r.score for r in rows] == [44, 37, 37]


def test_score_and_tier_shown_come_from_sonnet_run_one(rules):
    posts = [make_post("a", "A", 3)]
    runs = [make_run("a", 41, tier="Critical"), make_run("a", 22, tier="Medium", repeat=2)]
    (row,) = select_gift(posts, [yes("a")], runs, {}, rules)
    assert (row.score, row.tier) == (41, "Critical")


def test_posts_without_a_usable_sonnet_run_one_are_left_out(rules):
    posts = [make_post("failed", "F", 3), make_post("switched", "S", 3), make_post("missing", "M", 3)]
    failed = replace(make_run("failed", 40), structured_output=None, failure_reason="error_max_structured_output_retries")
    switched = replace(make_run("switched", 40), model_usage_keys=("claude-sonnet-5-5", "claude-haiku-5-5"))
    rows = select_gift(posts, [yes("failed"), yes("switched"), yes("missing")], [failed, switched], {}, rules)
    assert rows == []


def test_keeps_the_top_n(rules):
    posts = [make_post(f"p{i}", f"Co{i}", 1) for i in range(60)]
    runs = [make_run(f"p{i}", i % 51) for i in range(60)]
    rows = select_gift(posts, [yes(p.post_id) for p in posts], runs, {}, rules)
    assert len(rows) == 50
    assert rows[0].score == 50


def test_fewer_qualifiers_than_top_n_returns_them_all(rules):
    posts = [make_post("a", "A", 1), make_post("b", "B", 2)]
    rows = select_gift(posts, [yes("a"), yes("b")], [make_run("a", 30), make_run("b", 31)], {}, rules)
    assert _ids(rows) == ["b", "a"]


def test_row_has_exactly_the_locked_gift_fields(rules):
    post = make_post("a", "Acme Corp", 3, title="Account Executive", domain="acme.io")
    (row,) = select_gift([post], [yes("a", "ae_hiring")], [make_run("a", 42, tier="Critical")], {"a": passing_checks()}, rules)
    assert GIFT_FIELDS == (
        "company", "domain", "role_title", "post_url", "posted_date", "collection_date",
        "signal_type", "why_now", "score", "tier", "check_results",
    )
    assert row.as_dict() == {
        "company": "Acme Corp",
        "domain": "acme.io",
        "role_title": "Account Executive",
        "post_url": "https://boards.greenhouse.io/acmecorp/jobs/a",
        "posted_date": "2026-10-17",
        "collection_date": "2026-10-20",
        "signal_type": "ae_hiring",
        "why_now": 'Account Executive posted 3 days ago: "We are building our first outbound team to open new markets."',
        "score": 42,
        "tier": "Critical",
        "check_results": "evidence: pass; tier: fail; first_line_signal: pass (heuristic)",
    }
