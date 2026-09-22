import json
import re
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from src.classifiers.enums import ActivityType
from src.imports.base import (
    ActivitySourceAdapter,
    NormalizedActivity,
    SourceAccessDenied,
    fallback_external_id,
)

TOMSK = ZoneInfo("Asia/Tomsk")


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


class CultureRuAdapter(ActivitySourceAdapter):
    source_code = "culture_ru"
    name = "Культура.РФ"
    base_url = "https://www.culture.ru"

    async def fetch(self) -> list[dict]:
        html = await self.request_text("/afisha/tomskaya-oblast")
        return self._parse_html(html)

    @staticmethod
    def _parse_html(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        result = []
        for node in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(node.string or "null")
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type"):
                values = [data]
            elif isinstance(data, dict):
                values = data.get("itemListElement", [])
            elif isinstance(data, list):
                values = data
            else:
                values = [data]
            for value in values:
                value = value.get("item", value) if isinstance(value, dict) else value
                if isinstance(value, dict) and value.get("@type") in {
                    "Event",
                    "TheaterEvent",
                    "MusicEvent",
                    "ExhibitionEvent",
                }:
                    result.append(value)
        if not result:
            for link in soup.select('a[href*="/events/"]'):
                title = link.get_text(" ", strip=True)
                if title:
                    url = link.get("href", "")
                    result.append(
                        {
                            "@type": "Event",
                            "name": title,
                            "url": (
                                url if url.startswith("http") else CultureRuAdapter.base_url + url
                            ),
                        }
                    )
        return result

    def normalize(self, item: dict) -> NormalizedActivity:
        location = item.get("location") or {}
        address_data = location.get("address") or {}
        address = (
            address_data.get("streetAddress")
            if isinstance(address_data, dict)
            else str(address_data)
        )
        url = item.get("url") or self.base_url
        offers = item.get("offers") or {}
        price = offers.get("lowPrice", offers.get("price")) if isinstance(offers, dict) else None
        return NormalizedActivity(
            external_id=str(item.get("identifier") or fallback_external_id(url)),
            source_url=url,
            type=ActivityType.EVENT,
            title=item["name"].strip(),
            category_slug="культура",
            description=item.get("description"),
            address=address,
            price_from=Decimal(str(price)) if price is not None else None,
            is_free=float(price) == 0 if price is not None else None,
            image_url=item.get("image") if isinstance(item.get("image"), str) else None,
            registration_url=offers.get("url") if isinstance(offers, dict) else None,
            starts_at=utc_datetime(item.get("startDate")),
            ends_at=utc_datetime(item.get("endDate")),
            raw_payload=item,
        )


class TomskPfdoAdapter(ActivitySourceAdapter):
    source_code = "tomsk_pfdo"
    name = "Навигатор дополнительного образования Томской области"
    base_url = "https://tomsk.pfdo.ru"

    async def fetch(self) -> list[dict]:
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
            browser = await playwright.chromium.launch(headless=True, channel="chromium")
            try:
                page = await browser.new_page(user_agent=self.user_agent)
                await page.goto(
                    self.base_url + "/app/the-navigator/navigator",
                    wait_until="networkidle",
                    timeout=30_000,
                )
                html = await page.content()
            finally:
                await browser.close()
        return self._parse_html(html)

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
