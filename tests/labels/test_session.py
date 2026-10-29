"""Terminal labelling session: resumable, saves after every label, blind mode hides prior labels."""
import io
from datetime import date

from quality_gate.labels import export_sheet, run_session, validate_sheet
from quality_gate.types import HandLabel

from test_sheet import make_post

TODAY = date(2026, 10, 23)


def scripted(*answers):
    it = iter(answers)

    def ask(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None

    return ask


def setup(tmp_path, n=3):
    posts = [make_post(f"p{i}", text=f"Body text of post {i}.") for i in range(1, n + 1)]
    sheet = tmp_path / "sheet.csv"
    export_sheet(posts, sheet)
    return sheet, posts


def test_quit_then_resume_finishes_the_sheet(tmp_path):
    sheet, posts = setup(tmp_path)
    done = run_session(sheet, posts, today=TODAY, ask=scripted("y", "2", "q"), out=io.StringIO())
    assert done == 1
    out = io.StringIO()
    done = run_session(sheet, posts, today=TODAY, ask=scripted("n", "y", "4"), out=out)
    assert done == 2
    assert "Body text of post 1." not in out.getvalue()  # resumed after p1
    assert validate_sheet(sheet, ["p1", "p2", "p3"]) == [
        HandLabel("p1", True, "ae_hiring"),
        HandLabel("p2", False, "not_signal"),
        HandLabel("p3", True, "revops_gtm_eng"),
    ]


def test_label_is_saved_even_if_the_session_dies(tmp_path):
    sheet, posts = setup(tmp_path, n=2)
    run_session(sheet, posts, today=TODAY, ask=scripted("y", "1"), out=io.StringIO())  # EOF on p2
    assert "sdr_bdr_hiring" in sheet.read_text(encoding="utf-8")
    assert TODAY.isoformat() in sheet.read_text(encoding="utf-8")


def test_shows_post_text_from_the_local_cache(tmp_path):
    sheet, posts = setup(tmp_path, n=1)
    out = io.StringIO()
    run_session(sheet, posts, today=TODAY, ask=scripted("q"), out=out)
    assert "Body text of post 1." in out.getvalue()
    assert "Account Executive" in out.getvalue()


def test_bad_input_reprompts(tmp_path):
    sheet, posts = setup(tmp_path, n=1)
    run_session(sheet, posts, today=TODAY, ask=scripted("maybe", "y", "9", "3"), out=io.StringIO())
    assert validate_sheet(sheet, ["p1"]) == [HandLabel("p1", True, "sales_leadership")]


def test_text_after_an_answer_is_saved_as_a_note(tmp_path):
    sheet, posts = setup(tmp_path, n=2)
    run_session(sheet, posts, today=TODAY, ask=scripted("n unsure lang", "y", "2 founding AE"), out=io.StringIO())
    content = sheet.read_text(encoding="utf-8")
    assert "unsure lang" in content and "founding AE" in content
    assert validate_sheet(sheet, ["p1", "p2"])[1] == HandLabel("p2", True, "ae_hiring")


def test_blind_mode_hides_prior_labels(tmp_path):
    sheet, posts = setup(tmp_path, n=1)
    prior = {"p1": HandLabel("p1", True, "sales_leadership")}
    seen = io.StringIO()
    run_session(sheet, posts, today=TODAY, prior=prior, ask=scripted("q"), out=seen)
    assert "sales_leadership" in seen.getvalue()
    blind = io.StringIO()
    run_session(sheet, posts, today=TODAY, prior=prior, blind=True, ask=scripted("q"), out=blind)
    assert "sales_leadership" not in blind.getvalue()
    assert "prior label" not in blind.getvalue().lower()
