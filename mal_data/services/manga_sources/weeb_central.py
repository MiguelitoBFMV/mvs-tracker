import re
import time

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse

import requests

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class WeebCentralCandidate:
    source_id: str
    title: str
    url: str
    thumbnail_url: str | None = None


@dataclass(frozen=True)
class WeebCentralChapter:
    source_id: str
    label: str
    number: Decimal
    url: str
    published_at: datetime | None = None


class WeebCentralClient:
    BASE_URL = "https://weebcentral.com"
    SEARCH_URL = f"{BASE_URL}/search/data"

    REQUEST_INTERVAL_SECONDS = 2.05
    REQUEST_TIMEOUT_SECONDS = 30

    def __init__(self, session=None):
        self.session = session or requests.Session()
        self._last_request_at = None

        self.session.headers.update(
            {
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Referer": f"{self.BASE_URL}/",
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(X11; Linux x86_64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/150.0 Safari/537.36"
                ),
            }
        )

    def _wait_for_rate_limit(self):
        if self._last_request_at is None:
            return

        elapsed = (
            time.monotonic()
            - self._last_request_at
        )

        remaining = (
            self.REQUEST_INTERVAL_SECONDS
            - elapsed
        )

        if remaining > 0:
            time.sleep(remaining)

    def _get(self, url, *, params=None):
        self._wait_for_rate_limit()

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=(
                    self.REQUEST_TIMEOUT_SECONDS
                ),
            )
        finally:
            self._last_request_at = (
                time.monotonic()
            )

        if response.status_code == 429:
            raise RuntimeError(
                "Weeb Central rate limit reached "
                "(HTTP 429)."
            )

        response.raise_for_status()

        return response

    def search(
        self,
        query,
        *,
        page=1,
        limit=32,
    ):
        clean_query = " ".join(
            str(query).strip().split()
        )

        if not clean_query:
            return []

        response = self._get(
            self.SEARCH_URL,
            params={
                "text": clean_query,
                "limit": limit,
                "offset": (
                    max(page - 1, 0) * limit
                ),
                "display_mode": "Full Display",
            },
        )

        return self.parse_search_html(
            response.text
        )

    @classmethod
    def parse_search_html(cls, html):
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        candidates = []
        seen_ids = set()

        anchors = soup.select(
            (
                "article > section > "
                "a[href*='/series/']"
            )
        )

        for anchor in anchors:
            absolute_url = urljoin(
                cls.BASE_URL,
                anchor.get("href", ""),
            )

            source_id = (
                cls.extract_series_id(
                    absolute_url
                )
            )

            if (
                not source_id
                or source_id in seen_ids
            ):
                continue

            title_element = anchor.select_one(
                "div:not([class]):last-child"
            )

            title = (
                title_element.get_text(
                    " ",
                    strip=True,
                )
                if title_element
                else ""
            )

            if not title:
                title = anchor.get_text(
                    " ",
                    strip=True,
                )

            if not title:
                continue

            source_element = anchor.select_one(
                "source[srcset]"
            )
            image_element = anchor.select_one(
                "img[src]"
            )

            thumbnail_url = None

            if source_element:
                thumbnail_url = urljoin(
                    cls.BASE_URL,
                    source_element.get(
                        "srcset",
                        "",
                    ).split()[0],
                )

            elif image_element:
                thumbnail_url = urljoin(
                    cls.BASE_URL,
                    image_element.get(
                        "src",
                        "",
                    ),
                )

            candidates.append(
                WeebCentralCandidate(
                    source_id=source_id,
                    title=title,
                    url=absolute_url,
                    thumbnail_url=(
                        thumbnail_url or None
                    ),
                )
            )

            seen_ids.add(source_id)

        return candidates

    def fetch_chapters(self, series_url):
        chapter_list_url = (
            self.build_chapter_list_url(
                series_url
            )
        )

        response = self._get(
            chapter_list_url
        )

        return self.parse_chapter_list_html(
            response.text
        )

    def fetch_latest_chapter(
        self,
        series_url,
    ):
        chapters = self.fetch_chapters(
            series_url
        )

        if not chapters:
            return None

        return max(
            chapters,
            key=lambda chapter: (
                chapter.number,
                chapter.published_at
                or datetime.min,
            ),
        )

    @classmethod
    def parse_chapter_list_html(
        cls,
        html,
    ):
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        chapters = []

        for anchor in soup.select(
            "div[x-data] > a[href*='/chapters/']"
        ):
            label_element = anchor.select_one(
                "span.flex > span"
            )

            label = (
                label_element.get_text(
                    " ",
                    strip=True,
                )
                if label_element
                else anchor.get_text(
                    " ",
                    strip=True,
                )
            )

            chapter_number = (
                cls.parse_chapter_number(
                    label
                )
            )

            if chapter_number is None:
                continue

            absolute_url = urljoin(
                cls.BASE_URL,
                anchor.get("href", ""),
            )

            source_id = cls.extract_chapter_id(
                absolute_url
            )

            if not source_id:
                continue

            time_element = anchor.select_one(
                "time[datetime]"
            )

            published_at = (
                cls.parse_datetime(
                    time_element.get("datetime")
                )
                if time_element
                else None
            )

            chapters.append(
                WeebCentralChapter(
                    source_id=source_id,
                    label=label,
                    number=chapter_number,
                    url=absolute_url,
                    published_at=published_at,
                )
            )

        return chapters

    @staticmethod
    def parse_chapter_number(label):
        if not label:
            return None

        explicit_pattern = re.compile(
            (
                r"(?:chapter|ch\.?|episode|ep\.?"
                r"|round|smoke|hunt|days|#)"
                r"\s*([0-9]+(?:\.[0-9]+)?)"
            ),
            re.IGNORECASE,
        )

        explicit_match = (
            explicit_pattern.search(label)
        )

        raw_number = None

        if explicit_match:
            raw_number = (
                explicit_match.group(1)
            )
        else:
            generic_numbers = re.findall(
                r"[0-9]+(?:\.[0-9]+)?",
                label,
            )

            if generic_numbers:
                raw_number = (
                    generic_numbers[-1]
                )

        if raw_number is None:
            return None

        try:
            return Decimal(raw_number)

        except InvalidOperation:
            return None

    @staticmethod
    def parse_datetime(value):
        if not value:
            return None

        try:
            return datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError:
            return None

    @classmethod
    def build_chapter_list_url(
        cls,
        series_url,
    ):
        parsed = urlparse(series_url)

        if parsed.netloc not in {
            "weebcentral.com",
            "www.weebcentral.com",
        }:
            raise ValueError(
                "The URL does not belong to "
                "Weeb Central."
            )

        parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        if (
            len(parts) < 2
            or parts[0] != "series"
        ):
            raise ValueError(
                "Invalid Weeb Central "
                "series URL."
            )

        return (
            f"{cls.BASE_URL}/series/"
            f"{parts[1]}/full-chapter-list"
        )

    @staticmethod
    def extract_series_id(url):
        parts = [
            part
            for part in (
                urlparse(url).path.split("/")
            )
            if part
        ]

        if (
            len(parts) >= 2
            and parts[0] == "series"
        ):
            return parts[1]

        return None

    @staticmethod
    def extract_chapter_id(url):
        parts = [
            part
            for part in (
                urlparse(url).path.split("/")
            )
            if part
        ]

        if (
            len(parts) >= 2
            and parts[0] == "chapters"
        ):
            return parts[1]

        return None

