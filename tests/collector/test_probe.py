from quality_gate.collector import Board, list_url, probe

from .ats_fixtures import FIXTURES


def serving(responses):
    """A fetch callable that answers saved bodies by URL and 404s everything else."""
    calls = []

    def fetch(url):
        calls.append(url)
        name = responses.get(url)
        if name is None:
            return 404, None
        return 200, (FIXTURES / name).read_bytes()

    fetch.calls = calls
    return fetch


ACME = Board(ats="greenhouse", token="acme", company="Acme Robotics", domain="acme-robotics.example")


def test_probe_hit_returns_payload_for_matching_company():
    fetch = serving({list_url(ACME): "greenhouse_acme.json"})
    result = probe(ACME, fetch)

    assert result.status == "hit"
    assert result.payload["jobs"][0]["id"] == 4012345
    assert fetch.calls == [list_url(ACME)]  # one list call, nothing more


def test_probe_404_is_a_miss():
    result = probe(Board("ashby", "nosuchco", "No Such Co", "nosuch.co"), serving({}))

    assert result.status == "miss"
    assert result.payload is None


def test_probe_rejects_same_slug_board_of_a_different_company_by_greenhouse_company_name():
    fetch = serving({list_url(ACME): "greenhouse_acme_other_company.json"})

    assert probe(ACME, fetch).status == "wrong_company"


def test_probe_accepts_company_name_with_legal_suffix():
    board = Board(ats="greenhouse", token="acme", company="Acme Labs", domain="acmelabs.de")
    fetch = serving({list_url(board): "greenhouse_acme_other_company.json"})

    assert probe(board, fetch).status == "hit"


def test_probe_without_a_company_name_field_checks_the_post_text():
    initech = Board(ats="ashby", token="initech", company="Initech", domain="initech.com")
    impostor = Board(ats="ashby", token="initech", company="Initrode", domain="initrode.io")
    fetch = serving({list_url(initech): "ashby_initech.json"})

    assert probe(initech, fetch).status == "hit"
    assert probe(impostor, fetch).status == "wrong_company"


def test_slug_in_post_urls_does_not_count_as_the_company_name():
    initech = Board(ats="ashby", token="initech", company="Initech", domain="initech.com")
    fetch = serving({list_url(initech): "ashby_initech_other_company.json"})

    assert probe(initech, fetch).status == "wrong_company"
