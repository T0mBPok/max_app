from datetime import timedelta
from pathlib import Path

from src.imports.adapters import (
    AquatikaAdapter,
    DobroTomskAdapter,
    FiveVerstTrainingAdapter,
    FiveVerstVolunteerAdapter,
    TomskPfdoAdapter,
    TomskPhilharmonicAdapter,
    utc_datetime,
)
from src.imports.base import content_hash, fallback_external_id
from src.models import ActivityType

FIXTURES = Path(__file__).parent / "fixtures"


def test_local_html_fixtures_are_parsed_without_network():
    events = TomskPhilharmonicAdapter._parse_html(
        '<div class="poster__card" data-stamp="2610011900">'
        '<h5 class="poster__card-title">Концерт</h5>'
        '<span class="poster__card-date-date">1 октября 2026 | 19:00</span>'
        '<span class="poster__card-label">Большой концертный зал</span>'
        '<span class="poster__card-price-price">600–1500 руб.</span>'
        '<img src="https://example.com/poster.jpg">'
        '<a href="https://tomskfil.ru/afisha/concert/">Подробнее</a></div>'
    )
    pfdo = TomskPfdoAdapter._parse_html((FIXTURES / "pfdo.html").read_text(encoding="utf-8"))
    aquatika = AquatikaAdapter._parse_html((FIXTURES / "aquatika.html").read_text(encoding="utf-8"))
    assert events[0]["title"] == "Концерт"
    assert pfdo[0]["id"] == "program-7"
    assert aquatika == [{"title": "Плавание", "schedule": "Пн, Ср 18:00"}]


def test_philharmonic_normalization():
    item = TomskPhilharmonicAdapter().normalize(
        {
            "title": "Спектакль",
            "url": "https://tomskfil.ru/afisha/42/",
            "stamp": "2610011900",
            "date": "1 октября 2026 | 19:00",
            "price": "0 руб.",
        }
    )
    assert item.type == ActivityType.EVENT
    assert item.starts_at.hour == 12
    assert item.price_from == 0


def test_philharmonic_midnight_is_next_day():
    item = TomskPhilharmonicAdapter().normalize(
        {
            "title": "Ночной концерт",
            "url": "https://tomskfil.ru/afisha/night/",
            "stamp": "2610012400",
        }
    )
    assert item.starts_at.day == 1
    assert item.starts_at.hour == 17


def test_pfdo_normalization():
    item = TomskPfdoAdapter().normalize(
        {"id": "7", "url": "/program/7", "title": "Робототехника", "text": "Для детей 8–12 лет"}
    )
    assert item.type == ActivityType.COURSE
    assert (item.audience_min_age, item.audience_max_age) == (8, 12)


def test_pfdo_spa_json_is_parsed_and_deduplicated():
    items = TomskPfdoAdapter._parse_json(
        {
            "data": {
                "programs": [
                    {
                        "programId": 7,
                        "programName": "Робототехника",
                        "annotation": "Для детей 8–12 лет",
                    },
                    {"programId": 7, "programName": "Робототехника"},
                ]
            }
        }
    )
    assert len(items) == 1
    assert items[0]["url"] == "/app/the-navigator/program/7"


def test_pfdo_spa_json_does_not_treat_addresses_as_programs():
    items = TomskPfdoAdapter._parse_json(
        {
            "data": {
                "houses": [
                    {"id": 17, "name": "проспект Ленина, 36"},
                    {"id": 18, "name": "улица Усова, 15"},
                ]
            }
        }
    )
    assert items == []


def test_aquatika_normalization():
    item = AquatikaAdapter().normalize({"title": "Плавание", "schedule": "Пн, Ср 18:00"})
    assert item.type == ActivityType.SECTION
    assert item.schedule_text == "Пн, Ср 18:00"


def test_dobro_json_ld_event_is_parsed():
    html = """
    <script type="application/ld+json">
    [{"@type":"Event","name":"Помощь приюту","location":"Томская обл, г Томск",
      "startDate":"2026-10-03T12:00:00+07:00","endDate":"2026-10-03T16:00:00+07:00"}]
    </script>
    """
    raw = DobroTomskAdapter._parse_event_html(html, "https://dobro.ru/event/42")
    item = DobroTomskAdapter().normalize(raw)
    assert item.type == ActivityType.VOLUNTEERING
    assert item.address == "Томская обл, г Томск"
    assert item.starts_at.hour == 5


def test_five_verst_volunteer_dates_are_concrete():
    rows = FiveVerstVolunteerAdapter._parse_html(
        "<table><tr><th>Роль</th><th>26.09.2099</th></tr>"
        "<tr><td>Фотограф</td><td></td></tr></table>"
    )
    assert len(rows) == 1
    item = FiveVerstVolunteerAdapter().normalize(rows[0])
    assert item.type == ActivityType.VOLUNTEERING
    assert item.starts_at is not None
    assert item.address
    assert item.title == "Помощь в проведении «5 вёрст» — 26 сентября 2099"


def test_recurring_sources_stale_missing_slots_immediately():
    assert FiveVerstTrainingAdapter.stale_missing_immediately is True
    assert FiveVerstVolunteerAdapter.stale_missing_immediately is True


def test_dobro_can_legitimately_have_no_current_events():
    assert DobroTomskAdapter.allow_empty is True


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
