from checks_fixtures import label, make_run, output

from quality_gate.checks import check_label_signal, check_label_type


def test_matching_signal_and_type_pass():
    run = make_run()
    assert check_label_signal(run, label()).passed
    assert check_label_type(run, label()).passed
    assert check_label_signal(run, label()).name == "label_signal"
    assert check_label_type(run, label()).name == "label_type"


def test_signal_yes_vs_hand_label_no_fails_both():
    run = make_run()
    hand = label(signal=False, signal_type="not_signal")
    signal = check_label_signal(run, hand)
    assert not signal.passed
    assert "yes" in signal.reason and "no" in signal.reason
    assert not check_label_type(run, hand).passed


def test_right_yes_but_wrong_type_fails_only_the_type_check():
    run = make_run()
    hand = label(signal_type="ae_hiring")
    assert check_label_signal(run, hand).passed
    result = check_label_type(run, hand)
    assert not result.passed
    assert "sdr_bdr_hiring" in result.reason and "ae_hiring" in result.reason


def test_both_say_no_passes_both():
    run = make_run(output(signal=False, signal_type="not_signal", evidence=[]))
    hand = label(signal=False, signal_type="not_signal")
    assert check_label_signal(run, hand).passed
    assert check_label_type(run, hand).passed
