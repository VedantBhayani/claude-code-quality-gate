from datetime import date

from quality_gate.collector import Board, collect, list_url
from quality_gate.collector.cache import PoliteFetcher

from .ats_fixtures import FIXTURES

ACME = Board(ats="greenhouse", token="acme", company="Acme Robotics", domain="acme-robotics.example")


class FakeNet:
    """Stands in for the network: records requests, answers saved bodies, 404s the rest."""

    def __init__(self, bodies):
        self.bodies = bodies
        self.requests = []

    def __call__(self, url, headers):
        self.requests.append((url, headers))
        name = self.bodies.get(url)
        return (200, (FIXTURES / name).read_bytes()) if name else (404, None)


class FakeTime:
    def __init__(self):
        self.now = 100.0
        self.slept = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def fetcher(tmp_path, net, *, today=date(2026, 10, 22), time=None):
    time = time or FakeTime()
    return PoliteFetcher(tmp_path / "cache", transport=net, today=lambda: today,
                         sleep=time.sleep, clock=time.clock)


def test_collect_returns_posts_and_the_collection_date(tmp_path):
    net = FakeNet({list_url(ACME): "greenhouse_acme.json"})
    result = collect(ACME, fetcher(tmp_path, net))

    assert result.status == "hit"
    assert result.collection_date == date(2026, 10, 22)
    assert [p.post_id for p in result.posts] == ["greenhouse:acme:4012345"]
    assert all(p.collection_date == date(2026, 10, 22) for p in result.posts)


def test_requests_carry_a_descriptive_user_agent(tmp_path):
    net = FakeNet({list_url(ACME): "greenhouse_acme.json"})
    collect(ACME, fetcher(tmp_path, net))

    [(_, headers)] = net.requests
    assert "quality-gate" in headers["User-Agent"]
    assert "public job-board" in headers["User-Agent"]


def test_rerun_is_served_from_the_disk_cache_and_keeps_the_original_collection_date(tmp_path):
    net = FakeNet({list_url(ACME): "greenhouse_acme.json"})
    collect(ACME, fetcher(tmp_path, net, today=date(2026, 10, 22)))

    offline = FakeNet({})
    rerun = collect(ACME, fetcher(tmp_path, offline, today=date(2026, 11, 5)))

    assert offline.requests == []
    assert rerun.collection_date == date(2026, 10, 22)
    assert rerun.posts[0].collection_date == date(2026, 10, 22)


def test_consecutive_network_calls_are_spaced_about_one_second_apart(tmp_path):
    net = FakeNet({})
    time = FakeTime()
    fetch = fetcher(tmp_path, net, time=time)

    fetch("https://api.ashbyhq.com/posting-api/job-board/a")
    time.now += 0.25
    fetch("https://api.ashbyhq.com/posting-api/job-board/b")

    assert len(net.requests) == 2
    assert time.slept == [0.75]


def test_missing_board_is_reported_without_posts(tmp_path):
    result = collect(Board("lever", "nosuchco", "No Such Co", "nosuch.co"), fetcher(tmp_path, FakeNet({})))

    assert result.status == "miss"
    assert result.posts == []
