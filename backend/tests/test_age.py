from datetime import date

import pytest

from src.common.age import build_age_label, calculate_age, is_age_eligible, validate_age_range
from src.exceptions import AppError
from src.models import AgePreset


def test_age_before_and_on_birthday():
    born = date(2000, 9, 21)
    assert calculate_age(born, date(2026, 9, 20)) == 25
    assert calculate_age(born, date(2026, 9, 21)) == 26


def test_leap_day_birthday():
    born = date(2004, 2, 29)
    assert calculate_age(born, date(2025, 2, 28)) == 20
    assert calculate_age(born, date(2025, 3, 1)) == 21


def test_age_eligibility_and_open_range():
    assert is_age_eligible(17, 12, 17)
    assert not is_age_eligible(18, 12, 17)
    assert is_age_eligible(65, 60, None)


def test_range_crossing_adulthood_is_forbidden():
    with pytest.raises(AppError) as exc:
        validate_age_range(16, 20)
    assert exc.value.code == "INVALID_AGE_RANGE"


def test_age_label():
    assert build_age_label(60, None, AgePreset.SENIORS_60_PLUS) == "Старшее поколение 60+"
