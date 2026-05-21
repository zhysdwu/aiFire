import pytest

from apps.trends.services.scoring import clamp_score


@pytest.mark.django_db
def test_clamp_score():
    assert clamp_score(-1) == 0
    assert clamp_score(0) == 0
    assert clamp_score(50) == 50
    assert clamp_score(101) == 100
