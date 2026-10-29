import pytest

from gift_fixtures import GIFT_RULES


@pytest.fixture
def rules():
    return dict(GIFT_RULES)
