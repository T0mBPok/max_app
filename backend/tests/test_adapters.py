from datetime import timedelta
from pathlib import Path

from src.imports.adapters import AquatikaAdapter, CultureRuAdapter, TomskPfdoAdapter, utc_datetime
from src.imports.base import content_hash, fallback_external_id
from src.models import ActivityType

FIXTURES = Path(__file__).parent / "fixtures"


def test_local_html_fixtures_are_parsed_without_network():
    culture = CultureRuAdapter._parse_html((FIXTURES / "culture.html").read_text(encoding="utf-8"))
    pfdo = TomskPfdoAdapter._parse_html((FIXTURES / "pfdo.html").read_text(encoding="utf-8"))
    aquatika = AquatikaAdapter._parse_html((FIXTURES / "aquatika.html").read_text(encoding="utf-8"))
    assert culture[0]["identifier"] == "culture-42"
    assert pfdo[0]["id"] == "program-7"
    assert aquatika == [{"title": "Плавание", "schedule": "Пн, Ср 18:00"}]


def test_culture_normalization():
    item = CultureRuAdapter().normalize(
        {
            "identifier": "42",
            "name": "Спектакль",
            "url": "https://culture.ru/events/42",
            "startDate": "2026-10-01T19:00:00+07:00",
            "offers": {"price": 0},
        }
    )
    assert item.type == ActivityType.EVENT
    assert item.starts_at.hour == 12
    assert item.is_free is True


def test_pfdo_normalization():
    item = TomskPfdoAdapter().normalize(
        {"id": "7", "url": "/program/7", "title": "Робототехника", "text": "Для детей 8–12 лет"}
    )
    assert item.type == ActivityType.COURSE
    assert (item.audience_min_age, item.audience_max_age) == (8, 12)


def test_aquatika_normalization():
    item = AquatikaAdapter().normalize({"title": "Плавание", "schedule": "Пн, Ср 18:00"})
    assert item.type == ActivityType.SECTION
    assert item.schedule_text == "Пн, Ср 18:00"


def test_hash_and_fallback_id_are_stable():
    adapter = AquatikaAdapter()
    first = adapter.normalize({"title": "Плавание", "schedule": "Пн"})
    second = adapter.normalize({"title": "Плавание", "schedule": "Пн"})
    assert content_hash(first) == content_hash(second)
    assert fallback_external_id("HTTPS://EXAMPLE.COM/a/?utm=x") == fallback_external_id(
        "https://example.com/a"
    )


def test_tomsk_naive_datetime_becomes_utc():
    value = utc_datetime("2026-01-10T12:00:00")
    assert value.utcoffset() == timedelta(0)
    assert value.hour == 5
