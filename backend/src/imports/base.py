import asyncio
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from src.classifiers.enums import ActivityType
from src.config import get_settings


class SourceAccessDenied(RuntimeError):
    """Источник явно запретил автоматический доступ."""


@dataclass
class NormalizedActivity:
    external_id: str
    source_url: str
    type: ActivityType
    title: str
    category_slug: str
    city: str = "Томск"
    short_description: str | None = None
    description: str | None = None
    address: str | None = None
    price_from: Decimal | None = None
    price_to: Decimal | None = None
    is_free: bool | None = None
    audience_min_age: int | None = None
    audience_max_age: int | None = None
    image_url: str | None = None
    registration_url: str | None = None
    schedule_text: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    source_updated_at: datetime | None = None
    raw_payload: dict = field(default_factory=dict)


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def fallback_external_id(url: str | None, *stable_fields: str) -> str:
    value = canonical_url(url) if url else "|".join(x.strip().lower() for x in stable_fields)
    return hashlib.sha256(value.encode()).hexdigest()


def content_hash(item: NormalizedActivity) -> str:
    payload = asdict(item)
    payload.pop("raw_payload", None)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


class ActivitySourceAdapter(ABC):
    source_code: str
    name: str
    base_url: str
    user_agent = "PoidemBot/0.1"
    allow_empty = False
    stale_missing_immediately = False

    async def ensure_allowed(self, client: httpx.AsyncClient, url: str) -> None:
        cached_parser = getattr(self, "_robots_parser", None)
        if cached_parser is not None:
            if not cached_parser.can_fetch(self.user_agent, url):
                raise SourceAccessDenied("robots.txt запрещает автоматический доступ")
            return
        robots_url = urljoin(self.base_url, "/robots.txt")
        try:
            response = await client.get(robots_url)
            if response.status_code in {401, 403}:
                raise SourceAccessDenied("Источник запрещает автоматический доступ")
            if response.is_success:
                parser = RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(response.text.splitlines())
                self._robots_parser = parser
                if not parser.can_fetch(self.user_agent, url):
                    raise SourceAccessDenied("robots.txt запрещает автоматический доступ")
        except httpx.HTTPError:
            # Недоступный robots.txt сам по себе не означает запрет источника.
            return

    async def request_text(self, path: str) -> str:
        settings = get_settings()
        error: Exception | None = None
        async with httpx.AsyncClient(
            timeout=settings.parser_request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
        ) as client:
            target_url = urljoin(self.base_url, path)
            await self.ensure_allowed(client, target_url)
            for attempt in range(settings.parser_max_retries):
                try:
                    if settings.parser_request_delay_seconds:
                        await asyncio.sleep(settings.parser_request_delay_seconds)
                    response = await client.get(target_url)
                    response.raise_for_status()
                    return response.text
                except (httpx.HTTPError, TimeoutError) as exc:
                    error = exc
                    await asyncio.sleep(min(2**attempt, 8))
        reason = f"{type(error).__name__}: {error}" if error else "неизвестная ошибка"
        raise RuntimeError(f"Источник недоступен: {reason}")

    @abstractmethod
    async def fetch(self) -> list[dict]: ...

    @abstractmethod
    def normalize(self, item: dict) -> NormalizedActivity: ...
