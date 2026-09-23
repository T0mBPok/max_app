import asyncio
import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from src.classifiers.enums import ActivityType
from src.config import get_settings
from src.imports.base import (
    ActivitySourceAdapter,
    NormalizedActivity,
    SourceAccessDenied,
    fallback_external_id,
)

TOMSK = ZoneInfo("Asia/Tomsk")
RU_MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def utc_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TOMSK)
    return dt.astimezone(ZoneInfo("UTC"))


def age_range(text: str) -> tuple[int | None, int | None]:
    match = re.search(r"(\d{1,2})\s*[–—-]\s*(\d{1,2})", text)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)


def upcoming_weekdays(weekday: int, days: int | None = None) -> list[datetime]:
    days = days or get_settings().recurring_activity_horizon_days
    now = datetime.now(TOMSK)
    first = now + timedelta(days=(weekday - now.weekday()) % 7)
    return [first + timedelta(days=offset) for offset in range(0, days, 7)]


def tomsk_date_label(value: datetime) -> str:
    local = value.astimezone(TOMSK)
    return f"{local.day} {RU_MONTHS[local.month - 1]} {local.year}"


class TomskPhilharmonicAdapter(ActivitySourceAdapter):
    source_code = "tomsk_philharmonic"
    name = "Томская областная государственная филармония"
    base_url = "https://tomskfil.ru"

    async def fetch(self) -> list[dict]:
        html = await self.request_text("/afisha/")
        return self._parse_html(html)

    @staticmethod
    def _parse_html(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        result = []
        for card in soup.select(".poster__card"):
            title = card.select_one(".poster__card-title")
            link = card.select_one('a[href*="/afisha/"]')
            if not title or not link:
                continue
            image = card.select_one("img[src]")
            date = card.select_one(".poster__card-date-date")
            venue = card.select_one(".poster__card-label")
            price = card.select_one(".poster__card-price-price")
            result.append(
                {
                    "title": title.get_text(" ", strip=True),
                    "url": link.get("href"),
                    "image_url": image.get("src") if image else None,
                    "date": date.get_text(" ", strip=True) if date else None,
                    "stamp": card.get("data-stamp"),
                    "venue": venue.get_text(" ", strip=True) if venue else None,
                    "price": price.get_text(" ", strip=True) if price else None,
                }
            )
        return result

    def normalize(self, item: dict) -> NormalizedActivity:
        url = item["url"]
        if not url.startswith("http"):
            url = self.base_url + "/" + url.lstrip("/")
        prices = [
            Decimal(value.replace(",", "."))
            for value in re.findall(r"\d+[.,]?\d*", item.get("price") or "")
        ]
        starts_at = None
        if item.get("stamp"):
            stamp = item["stamp"]
            if stamp.endswith("2400"):
                starts_at = datetime.strptime(stamp[:6], "%y%m%d") + timedelta(days=1)
            else:
                starts_at = datetime.strptime(stamp, "%y%m%d%H%M")
            starts_at = starts_at.replace(tzinfo=TOMSK)
            starts_at = starts_at.astimezone(ZoneInfo("UTC"))
        return NormalizedActivity(
            external_id=fallback_external_id(url),
            source_url=url,
            type=ActivityType.EVENT,
            title=item["title"].strip(),
            category_slug="культура",
            address=item.get("venue"),
            price_from=min(prices) if prices else None,
            price_to=max(prices) if prices else None,
            is_free="бесплат" in (item.get("price") or "").lower(),
            image_url=item.get("image_url"),
            registration_url=url,
            schedule_text=item.get("date"),
            starts_at=starts_at,
            raw_payload=item,
        )


class TomskPfdoAdapter(ActivitySourceAdapter):
    source_code = "tomsk_pfdo"
    name = "Навигатор дополнительного образования Томской области"
    base_url = "https://tomsk.pfdo.ru"

    async def fetch(self) -> list[dict]:
        payload_items: list[dict] = []
        response_tasks: list[asyncio.Task] = []

        async def collect_response(response) -> None:
            content_type = response.headers.get("content-type", "")
            url = response.url.lower()
            if "json" not in content_type or not any(
                marker in url for marker in ("program", "navigator", "search", "catalog")
            ):
                return
            try:
                payload_items.extend(self._parse_json(await response.json()))
            except Exception:
                return

        try:
            html = await self.request_text("/app/the-navigator/navigator")
        except SourceAccessDenied:
            raise
        except RuntimeError:
            html = ""
        result = self._parse_html(html)
        if result:
            return result
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=self.user_agent)
                page.on(
                    "response",
                    lambda response: response_tasks.append(
                        asyncio.create_task(collect_response(response))
                    ),
                )
                try:
                    await page.goto(
                        self.base_url + "/app/the-navigator/navigator",
                        wait_until="domcontentloaded",
                        timeout=45_000,
                    )
                except PlaywrightTimeoutError:
                    # SPA может держать соединения открытыми; уже загруженный DOM всё равно полезен.
                    pass
                for _ in range(4):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1_000)
                html = await page.content()
                if response_tasks:
                    await asyncio.gather(*response_tasks, return_exceptions=True)
            finally:
                await browser.close()
        return self._deduplicate([*payload_items, *self._parse_html(html)])

    @staticmethod
    def _deduplicate(items: list[dict]) -> list[dict]:
        result = []
        seen = set()
        for item in items:
            key = str(item.get("id") or item.get("url") or item.get("title"))
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result

    @classmethod
    def _parse_json(cls, payload, context: str = "") -> list[dict]:
        result = []
        if isinstance(payload, list):
            for value in payload:
                result.extend(cls._parse_json(value, context))
            return cls._deduplicate(result)
        if not isinstance(payload, dict):
            return result

        title = next(
            (
                payload.get(key)
                for key in ("title", "name", "programName")
                if isinstance(payload.get(key), str) and payload[key].strip()
            ),
            None,
        )
        identifier = next(
            (payload.get(key) for key in ("id", "programId", "uuid") if payload.get(key)),
            None,
        )
        url = next(
            (
                payload.get(key)
                for key in ("url", "href", "link")
                if isinstance(payload.get(key), str)
            ),
            None,
        )
        url_is_program = isinstance(url, str) and "program" in url.lower()
        explicit_program_fields = "programId" in payload or "programName" in payload
        program_context = "program" in context.lower()
        program_details = bool(
            {"description", "annotation", "ageRange", "direction", "programType"} & payload.keys()
        )
        is_program = (
            explicit_program_fields or url_is_program or (program_context and program_details)
        )
        if title and (identifier or url) and is_program:
            text_parts = [
                str(payload[key])
                for key in ("description", "annotation", "age", "ageRange")
                if payload.get(key)
            ]
            result.append(
                {
                    "id": identifier,
                    "url": url or f"/app/the-navigator/program/{identifier}",
                    "title": title,
                    "text": " ".join(text_parts) or title,
                }
            )
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                result.extend(cls._parse_json(value, str(key)))
        return cls._deduplicate(result)

    @staticmethod
    def _parse_html(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        result = []
        for card in soup.select("[data-program-id], .program-card, .navigator-program"):
            link = card.select_one("a[href]")
            title = card.select_one("h2, h3, .title, [class*=title]")
            if link and title:
                result.append(
                    {
                        "id": card.get("data-program-id"),
                        "url": link.get("href"),
                        "title": title.get_text(" ", strip=True),
                        "text": card.get_text(" ", strip=True),
                    }
                )
        if not result:
            for link in soup.select('a[href*="program"]'):
                title = link.get_text(" ", strip=True)
                if title:
                    result.append(
                        {
                            "id": None,
                            "url": link.get("href"),
                            "title": title,
                            "text": link.parent.get_text(" ", strip=True),
                        }
                    )
        return result

    def normalize(self, item: dict) -> NormalizedActivity:
        url = item["url"] if item["url"].startswith("http") else self.base_url + item["url"]
        min_age, max_age = age_range(item.get("text", ""))
        return NormalizedActivity(
            external_id=str(item.get("id") or fallback_external_id(url)),
            source_url=url,
            type=ActivityType.COURSE,
            title=item["title"].strip(),
            category_slug="образование",
            short_description=item.get("text"),
            audience_min_age=min_age,
            audience_max_age=max_age,
            registration_url=url,
            raw_payload=item,
        )


class AquatikaAdapter(ActivitySourceAdapter):
    source_code = "aquatika"
    name = "СК «Акватика»"
    base_url = "https://акватика.рф"

    async def fetch(self) -> list[dict]:
        html = await self.request_text("/irkutskiy/shedule")
        return self._parse_html(html)

    @staticmethod
    def _parse_html(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        result = []
        for row in soup.select("table tr"):
            cells = [x.get_text(" ", strip=True) for x in row.select("th, td")]
            if len(cells) >= 2 and cells[0].lower() not in {"занятие", "наименование"}:
                result.append({"title": cells[0], "schedule": " · ".join(cells[1:])})
        if not result:
            result.append(
                {
                    "title": "Плавание и занятия в СК «Акватика»",
                    "schedule": soup.get_text(" ", strip=True)[:1500],
                }
            )
        return result

    def normalize(self, item: dict) -> NormalizedActivity:
        url = self.base_url + "/irkutskiy/shedule"
        title = item["title"].strip()
        return NormalizedActivity(
            external_id=fallback_external_id(None, title, item.get("schedule", "")),
            source_url=url,
            type=ActivityType.SECTION,
            title=title,
            category_slug="плавание",
            city="Томск",
            address="Иркутский тракт, 51/3",
            schedule_text=item.get("schedule"),
            raw_payload=item,
        )


class DobroTomskAdapter(ActivitySourceAdapter):
    source_code = "dobro_tomsk"
    name = "Добро.рф — Томская область"
    base_url = "https://dobro.ru"
    # У конкретной организации может не быть текущих коротких мероприятий.
    # Это нормальный успешный ответ источника, а не поломка парсера.
    allow_empty = True
    organization_path = "/organizations/1320697/events"

    async def fetch(self) -> list[dict]:
        html = await self.request_text(self.organization_path)
        event_ids = sorted(set(re.findall(r"/event/(\d+)", html)))[:20]
        semaphore = asyncio.Semaphore(3)

        async def load_event(event_id: str) -> tuple[bool, dict | None]:
            try:
                async with semaphore:
                    detail_html = await self.request_text(f"/event/{event_id}")
            except RuntimeError:
                return False, None
            item = self._parse_event_html(detail_html, f"{self.base_url}/event/{event_id}")
            if item and self._is_concrete_future_tomsk_event(item):
                return True, item
            return True, None

        values = await asyncio.gather(*(load_event(event_id) for event_id in event_ids))
        if event_ids and not any(loaded for loaded, _ in values):
            raise RuntimeError("Не удалось загрузить карточки мероприятий")
        return [item for _, item in values if item]

    @staticmethod
    def _parse_event_html(html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "lxml")
        for node in soup.select('script[type="application/ld+json"]'):
            try:
                payload = json.loads(node.string or "null")
            except json.JSONDecodeError:
                continue
            values = payload if isinstance(payload, list) else [payload]
            for value in values:
                if isinstance(value, dict) and value.get("@type") == "Event":
                    return {**value, "url": url}
        return None

    @staticmethod
    def _is_concrete_future_tomsk_event(item: dict) -> bool:
        starts_at = utc_datetime(item.get("startDate"))
        ends_at = utc_datetime(item.get("endDate"))
        location = str(item.get("location") or "")
        if not starts_at or not location or "томск" not in location.lower():
            return False
        if (ends_at or starts_at) < datetime.now(ZoneInfo("UTC")):
            return False
        return not ends_at or ends_at - starts_at <= timedelta(days=7)

    def normalize(self, item: dict) -> NormalizedActivity:
        url = item["url"]
        image = item.get("image")
        if isinstance(image, list):
            image = image[0] if image else None
        return NormalizedActivity(
            external_id=fallback_external_id(url),
            source_url=url,
            type=ActivityType.VOLUNTEERING,
            title=item["name"].strip(),
            category_slug="волонтёрство",
            description=item.get("description"),
            address=str(item.get("location")),
            is_free=True,
            image_url=image if isinstance(image, str) else None,
            registration_url=url,
            starts_at=utc_datetime(item.get("startDate")),
            ends_at=utc_datetime(item.get("endDate")),
            raw_payload=item,
        )


class FiveVerstTrainingAdapter(ActivitySourceAdapter):
    source_code = "five_verst_tomsk_training"
    name = "5 вёрст — Томск Сосновый Бор"
    base_url = "https://5verst.ru"
    stale_missing_immediately = True
    page_path = "/tomsksosnovybor/"
    address = "Томск, улица Кутузова, 1Б"

    async def fetch(self) -> list[dict]:
        html = await self.request_text(self.page_path)
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True).lower()
        if "каждую субботу" not in text and "каждой суббот" not in text:
            return []
        result = []
        for value in upcoming_weekdays(5):
            hour, minute = (9, 0) if 3 <= value.month <= 10 else (9, 30)
            starts_at = value.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if starts_at <= datetime.now(TOMSK):
                starts_at += timedelta(days=7)
            if any(row["starts_at"] == starts_at.isoformat() for row in result):
                continue
            result.append({"starts_at": starts_at.isoformat()})
        return result

    def normalize(self, item: dict) -> NormalizedActivity:
        starts_at = utc_datetime(item["starts_at"])
        url = self.base_url + self.page_path
        return NormalizedActivity(
            external_id=fallback_external_id(None, self.source_code, starts_at.isoformat()),
            source_url=url,
            type=ActivityType.SECTION,
            title=f"Дружеский старт «5 вёрст» — {tomsk_date_label(starts_at)}",
            category_slug="спорт",
            short_description="Бесплатный забег или прогулка на 5 км в Сосновом Бору.",
            address=self.address,
            is_free=True,
            registration_url=url,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1, minutes=30),
            raw_payload=item,
        )


class FiveVerstVolunteerAdapter(ActivitySourceAdapter):
    source_code = "five_verst_tomsk_volunteer"
    name = "5 вёрст — волонтёрство в Томске"
    base_url = "https://5verst.ru"
    stale_missing_immediately = True
    page_path = "/tomsksosnovybor/volunteer/"
    address = FiveVerstTrainingAdapter.address

    async def fetch(self) -> list[dict]:
        html = await self.request_text(self.page_path)
        return self._parse_html(html)

    @staticmethod
    def _parse_html(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        result = []
        for heading in soup.select("table tr:first-child th, table tr:first-child td"):
            value = heading.get_text(" ", strip=True)
            try:
                day = datetime.strptime(value, "%d.%m.%Y").replace(tzinfo=TOMSK)
            except ValueError:
                continue
            hour, minute = (9, 0) if 3 <= day.month <= 10 else (9, 30)
            starts_at = day.replace(hour=hour, minute=minute)
            if starts_at > datetime.now(TOMSK):
                result.append({"starts_at": starts_at.isoformat()})
        return result

    def normalize(self, item: dict) -> NormalizedActivity:
        starts_at = utc_datetime(item["starts_at"])
        url = self.base_url + self.page_path
        return NormalizedActivity(
            external_id=fallback_external_id(None, self.source_code, starts_at.isoformat()),
            source_url=url,
            type=ActivityType.VOLUNTEERING,
            title=f"Помощь в проведении «5 вёрст» — {tomsk_date_label(starts_at)}",
            category_slug="волонтёрство",
            short_description="Организатор, секундомер, фотограф, маршал и другие роли.",
            address=self.address,
            is_free=True,
            registration_url=url,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1, minutes=30),
            raw_payload=item,
        )
