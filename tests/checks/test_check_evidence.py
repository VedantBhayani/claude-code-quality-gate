from checks_fixtures import make_post, make_run, output

from quality_gate.checks import check_evidence


def test_quote_found_despite_curly_apostrophe_dash_and_whitespace_differences():
    run = make_run(output(evidence=["We're building our first outbound team - and we need help."]))
    result = check_evidence(run, make_post())
    assert result.name == "evidence"
    assert result.passed, result.reason


def test_a_quote_not_in_the_post_fails_and_names_the_quote():
    run = make_run(output(evidence=["We're building our first outbound team", "Series B funded"]))
    result = check_evidence(run, make_post())
    assert not result.passed
    assert "Series B funded" in result.reason


def test_case_is_not_ignored_because_quotes_must_be_verbatim():
    run = make_run(output(evidence=["WE'RE BUILDING OUR FIRST OUTBOUND TEAM"]))
    assert not check_evidence(run, make_post()).passed


def test_signal_yes_with_no_quotes_fails():
    run = make_run(output(evidence=[]))
    result = check_evidence(run, make_post())
    assert not result.passed
    assert "no evidence" in result.reason


def test_signal_no_with_no_quotes_passes():
    run = make_run(output(signal=False, signal_type="not_signal", evidence=[]))
    assert check_evidence(run, make_post()).passed


def test_an_empty_quote_does_not_count_as_found():
    run = make_run(output(evidence=["  "]))
    assert not check_evidence(run, make_post()).passed
