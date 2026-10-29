"""Comparison metrics on small hand-computed tables. Expected values are worked by hand."""
import pytest

from quality_gate.metrics import cohens_kappa, flip_rate, macro_f1, per_population, repeat_noise


def _table(cells):
    """Build two raters' label maps from (label_a, label_b, count) cells."""
    a, b, i = {}, {}, 0
    for la, lb, count in cells:
        for _ in range(count):
            a[f"p{i}"], b[f"p{i}"] = la, lb
            i += 1
    return a, b


def test_kappa_textbook_yes_no_table():
    # 50 items: yes/yes 20, yes/no 5, no/yes 10, no/no 15.
    # p_o = 35/50 = 0.70; p_e = 0.5*0.6 + 0.5*0.4 = 0.50; kappa = 0.20/0.50 = 0.40.
    a, b = _table([(True, True, 20), (True, False, 5), (False, True, 10), (False, False, 15)])
    result = cohens_kappa(a, b)
    assert result.kappa == pytest.approx(0.40)
    assert result.observed_agreement == pytest.approx(0.70)
    assert result.n == 50


def test_kappa_second_textbook_table():
    # 100 items: yes/yes 45, yes/no 15, no/yes 25, no/no 15.
    # p_o = 0.60; p_e = 0.6*0.7 + 0.4*0.3 = 0.54; kappa = 0.06/0.46 = 0.130435.
    a, b = _table([(True, True, 45), (True, False, 15), (False, True, 25), (False, False, 15)])
    assert cohens_kappa(a, b).kappa == pytest.approx(0.06 / 0.46)


def test_kappa_on_signal_type_three_classes():
    # 10 items. Rater A: ae x4, sdr x3, not x3. Rater B: ae x4, sdr x4, not x2.
    # Cells: ae/ae 3, ae/sdr 1, sdr/sdr 3, not/ae 1, not/not 2 -> p_o = 8/10.
    # p_e = (4*4 + 3*4 + 3*2)/100 = 0.34; kappa = 0.46/0.66.
    a, b = _table([
        ("ae_hiring", "ae_hiring", 3), ("ae_hiring", "sdr_bdr_hiring", 1),
        ("sdr_bdr_hiring", "sdr_bdr_hiring", 3), ("not_signal", "ae_hiring", 1),
        ("not_signal", "not_signal", 2),
    ])
    assert cohens_kappa(a, b).kappa == pytest.approx(0.46 / 0.66)


def test_kappa_all_agree_is_one_even_with_a_single_category():
    a, b = _table([(True, True, 7)])
    assert cohens_kappa(a, b).kappa == 1.0
    a, b = _table([(True, True, 4), (False, False, 3)])
    assert cohens_kappa(a, b).kappa == 1.0


def test_kappa_ignores_posts_either_rater_failed_on():
    a, b = _table([(True, True, 20), (True, False, 5), (False, True, 10), (False, False, 15)])
    a["failed"], b["failed"] = None, True
    a["only_a"] = True
    assert cohens_kappa(a, b).n == 50
    assert cohens_kappa(a, b).kappa == pytest.approx(0.40)


HAIKU, SONNET, HAIKU_OLD = "claude-haiku-5-5", "claude-sonnet-5-5", "claude-haiku-4-5-20251001"


def test_flip_rate_counts_changed_labels_and_failures_per_model():
    # 6 posts. p1..p4 labelled by both; p2 and p4 change -> 2/4 = 0.5.
    # Haiku failed on p5; Sonnet failed on p6 and has no run at all for p5.
    haiku = {"p1": True, "p2": True, "p3": False, "p4": False, "p5": None, "p6": True}
    sonnet = {"p1": True, "p2": False, "p3": False, "p4": True, "p6": None}
    result = flip_rate(HAIKU, haiku, SONNET, sonnet)
    assert (result.changed, result.n, result.rate) == (2, 4, 0.5)
    assert result.failures == {HAIKU: 1, SONNET: 2}
    assert result.kind == "model switch"


def test_flip_rate_between_versions_of_one_model_is_a_model_upgrade():
    old = {"p1": True, "p2": False, "p3": True, "p4": True}
    new = {"p1": True, "p2": False, "p3": False, "p4": True}
    result = flip_rate(HAIKU_OLD, old, HAIKU, new)
    assert result.kind == "model upgrade"
    assert result.rate == 0.25
    assert "drift" not in result.describe()
    assert "model upgrade" in result.describe()


def test_repeat_noise_is_the_share_changed_between_two_runs_of_one_model():
    run1 = {"p1": "ae_hiring", "p2": "not_signal", "p3": "sdr_bdr_hiring", "p4": None, "p5": "ae_hiring"}
    run2 = {"p1": "ae_hiring", "p2": "ae_hiring", "p3": "sdr_bdr_hiring", "p4": "ae_hiring", "p5": "ae_hiring"}
    result = repeat_noise(SONNET, run1, run2)
    assert (result.changed, result.n, result.rate) == (1, 4, 0.25)
    assert result.kind == "repeat noise"
    assert result.failures == {"run 1": 1, "run 2": 0}


def test_macro_f1_on_yes_no():
    # gold T,T,F,F; pred T,F,F,F. yes: P=1, R=1/2, F1=2/3. no: P=2/3, R=1, F1=4/5.
    # macro = (2/3 + 4/5)/2 = 11/15.
    gold = {"p1": True, "p2": True, "p3": False, "p4": False}
    pred = {"p1": True, "p2": False, "p3": False, "p4": False}
    result = macro_f1(pred, gold)
    assert result.macro_f1 == pytest.approx(11 / 15)
    assert result.per_class[True] == pytest.approx(2 / 3)
    assert result.n == 4


def test_macro_f1_on_signal_type_scores_a_never_predicted_class_as_zero():
    # gold ae,ae,sdr,not; pred ae,sdr,sdr,ae.
    # ae: tp1 fp1 fn1 -> 1/2. sdr: tp1 fp1 fn0 -> 2/3. not: tp0 fn1 -> 0. macro = 7/18.
    gold = {"p1": "ae_hiring", "p2": "ae_hiring", "p3": "sdr_bdr_hiring", "p4": "not_signal"}
    pred = {"p1": "ae_hiring", "p2": "sdr_bdr_hiring", "p3": "sdr_bdr_hiring", "p4": "ae_hiring"}
    result = macro_f1(pred, gold)
    assert result.macro_f1 == pytest.approx(7 / 18)
    assert result.per_class["not_signal"] == 0.0


def test_macro_f1_counts_failed_runs_and_skips_unlabelled_posts():
    gold = {"p1": True, "p2": True, "p3": False, "p4": False, "p5": True}
    pred = {"p1": True, "p2": False, "p3": False, "p4": False, "p5": None, "unlabelled": True}
    result = macro_f1(pred, gold)
    assert result.n == 4
    assert result.failures == 1
    assert result.macro_f1 == pytest.approx(11 / 15)


def test_metrics_are_computed_per_population():
    haiku = {"n1": True, "n2": True, "n3": False, "n4": False, "a1": True, "a2": False}
    sonnet = {"n1": True, "n2": True, "n3": False, "n4": True, "a1": False, "a2": True}
    populations = {"natural sample": ["n1", "n2", "n3", "n4"], "ambiguous subset": ["a1", "a2", "a3"]}
    results = per_population(populations, flip_rate, HAIKU, haiku, SONNET, sonnet)
    assert results["natural sample"].rate == 0.25
    assert results["ambiguous subset"].rate == 1.0
    # a3 is in the population but neither arm has a run for it: a failure on both sides.
    assert results["ambiguous subset"].failures == {HAIKU: 1, SONNET: 1}


def test_per_population_works_for_label_only_metrics():
    gold = {"n1": True, "n2": False, "a1": True}
    pred = {"n1": True, "n2": False, "a1": False}
    results = per_population({"natural sample": ["n1", "n2"], "ambiguous subset": ["a1"]}, macro_f1, pred, gold)
    assert results["natural sample"].macro_f1 == 1.0
    assert results["ambiguous subset"].macro_f1 == 0.0


def test_flip_rate_refuses_the_same_model_on_both_sides():
    with pytest.raises(ValueError, match="repeat_noise"):
        flip_rate(HAIKU, {"p1": True}, HAIKU, {"p1": True})
