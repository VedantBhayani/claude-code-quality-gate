from datetime import date

import pytest

from quality_gate.config import load_config
from quality_gate.sampler import SampleSizeError, draw_samples
from quality_gate.types import Post

CORE_TITLES = ["Account Executive", "SDR", "Head of Sales", "BDR", "Enterprise Sales Manager"]
AMBIGUOUS_TITLES = ["Account Manager", "Customer Success Manager", "Sales Engineer", "Partnerships Lead", "RevOps Manager"]
OUT_TITLES = ["Software Engineer", "Product Designer", "Finance Manager"]


def _post(i: int, title: str) -> Post:
    return Post(
        post_id=f"p{i:03d}", company=f"Co{i % 7}", domain=f"co{i % 7}.com", title=title,
        url=f"https://boards.example/{i}", post_date=date(2026, 10, 1),
        collection_date=date(2026, 10, 20), ats="greenhouse", text="...",
    )


def _pool(n_core=60, n_amb=20, n_out=15):
    posts, i = [], 0
    for titles, n in ((CORE_TITLES, n_core), (AMBIGUOUS_TITLES, n_amb), (OUT_TITLES, n_out)):
        for k in range(n):
            posts.append(_post(i, titles[k % len(titles)]))
            i += 1
    return posts


@pytest.fixture
def cfg(package_root):
    return load_config(package_root)


def test_ambiguous_roles_go_only_to_the_ambiguous_subset(cfg):
    s = draw_samples(_pool(), cfg, natural_size=60, ambiguous_size=20)
    assert {p.title for p in s.natural} <= set(CORE_TITLES)
    assert {p.title for p in s.ambiguous} <= set(AMBIGUOUS_TITLES)
    assert len(s.natural) == 60 and len(s.ambiguous) == 20


def test_opus_subset_is_50_posts_from_the_natural_sample(cfg):
    s = draw_samples(_pool(), cfg, natural_size=60, ambiguous_size=10)
    assert len(s.opus) == 50
    assert len({p.post_id for p in s.opus}) == 50
    assert {p.post_id for p in s.opus} <= {p.post_id for p in s.natural}


def test_same_seed_gives_the_same_samples_whatever_the_input_order(cfg):
    pool = _pool()
    a = draw_samples(pool, cfg, natural_size=55, ambiguous_size=12)
    b = draw_samples(list(reversed(pool)), cfg, natural_size=55, ambiguous_size=12)
    assert [p.post_id for p in a.natural] == [p.post_id for p in b.natural]
    assert [p.post_id for p in a.ambiguous] == [p.post_id for p in b.ambiguous]
    assert [p.post_id for p in a.opus] == [p.post_id for p in b.opus]


def test_a_different_seed_gives_a_different_natural_sample(cfg):
    pool = _pool()
    a = draw_samples(pool, cfg, natural_size=55, ambiguous_size=12)
    b = draw_samples(pool, cfg, natural_size=55, ambiguous_size=12, seeds={"natural_sample": 1})
    assert [p.post_id for p in a.natural] != [p.post_id for p in b.natural]


@pytest.mark.parametrize("sizes, expected", [
    ({"natural_size": 61, "ambiguous_size": 5}, "natural.*61.*only 60"),
    ({"natural_size": 60, "ambiguous_size": 21}, "ambiguous.*21.*only 20"),
])
def test_a_size_larger_than_the_pool_fails_clearly(cfg, sizes, expected):
    with pytest.raises(SampleSizeError, match=expected):
        draw_samples(_pool(), cfg, **sizes)


def test_natural_sample_smaller_than_the_opus_subset_fails_clearly(cfg):
    with pytest.raises(SampleSizeError, match="opus.*50.*only 40"):
        draw_samples(_pool(), cfg, natural_size=40, ambiguous_size=5)
