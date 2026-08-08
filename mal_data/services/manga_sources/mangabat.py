import re
import time
import unicodedata

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse

import requests

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class MangabatCandidate:
    source_id: str
    title: str
    url: str
    thumbnail_url: str | None = None


@dataclass(frozen=True)
class MangabatChapter:
    source_id: str
    label: str
    number: Decimal
    url: str
    published_at: datetime | None = None


class MangabatClient:
    BASE_URL = "https://www.mangabats.com"
    SEARCH_PATH = "/search/story"

    REQUEST_INTERVAL_SECONDS = 1.05
    REQUEST_TIMEOUT_SECONDS = 30

    ACCEPTED_HOSTS = {
        "mangabats.com",
        "www.mangabats.com",
    }

    def __init__(self, session=None):
        self.session = (
            session
            or requests.Session()
        )
        self._last_request_at = None

        self.session.headers.update(
            {
                "Accept": (
                    "text/html,"
                    "application/json;q=0.9,"
                    "*/*;q=0.8"
                ),
                "Accept-Language": (
                    "en-US,en;q=0.9"
                ),
                "Referer": (
                    f"{self.BASE_URL}/"
                ),
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

    def _get(
        self,
        url,
        *,
        params=None,
    ):
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

        if response.status_code == 403:
            raise RuntimeError(
                "Mangabat rejected the request "
                "(HTTP 403)."
            )

        if response.status_code == 429:
            raise RuntimeError(
                "Mangabat rate limit reached "
                "(HTTP 429)."
            )

        response.raise_for_status()

        return response

    @classmethod
    def build_series_url(
        cls,
        slug,
    ):
        return (
            f"{cls.BASE_URL}/manga/"
            f"{slug}"
        )

    @classmethod
    def build_chapter_url(
        cls,
        manga_slug,
        chapter_slug,
    ):
        return (
            f"{cls.BASE_URL}/manga/"
            f"{manga_slug}/"
            f"{chapter_slug}"
        )

    @classmethod
    def extract_title_id(
        cls,
        value,
    ):
        clean_value = str(
            value
        ).strip()

        if not clean_value:
            return None

        parsed = urlparse(
            clean_value
        )

        if parsed.scheme:
            if (
                parsed.netloc
                not in cls.ACCEPTED_HOSTS
            ):
                return None

            parts = [
                part
                for part in (
                    parsed.path.split("/")
                )
                if part
            ]

            if (
                len(parts) >= 2
                and parts[0] == "manga"
            ):
                return parts[1]

            return None

        if (
            "/" not in clean_value
            and " " not in clean_value
            and re.fullmatch(
                r"[a-z0-9][a-z0-9_-]*",
                clean_value,
                re.IGNORECASE,
            )
            and (
                "-" in clean_value
                or "_" in clean_value
                or any(
                    character.isdigit()
                    for character
                    in clean_value
                )
            )
        ):
            return clean_value

        return None

    @staticmethod
    def normalize_search_query(
        query,
    ):
        normalized = (
            unicodedata.normalize(
                "NFKD",
                str(query).lower(),
            )
            .encode(
                "ascii",
                "ignore",
            )
            .decode("ascii")
        )

        normalized = re.sub(
            r"[^a-z0-9]+",
            "_",
            normalized,
        )

        return normalized.strip("_")

    def search(
        self,
        query,
    ):
        clean_query = " ".join(
            str(query).strip().split()
        )

        if not clean_query:
            return []

        direct_slug = (
            self.extract_title_id(
                clean_query
            )
        )

        if direct_slug:
            candidate = (
                self.fetch_candidate(
                    direct_slug
                )
            )

            return (
                [candidate]
                if candidate
                else []
            )

        normalized_query = (
            self.normalize_search_query(
                clean_query
            )
        )

        if not normalized_query:
            return []

        search_url = (
            f"{self.BASE_URL}"
            f"{self.SEARCH_PATH}/"
            f"{normalized_query}"
        )

        response = self._get(
            search_url,
            params={
                "page": 1,
            },
        )

        return self.parse_search_html(
            response.text
        )

    @classmethod
    def parse_search_html(
        cls,
        html,
    ):
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        selectors = (
            ".panel_story_list .story_item, "
            "div.list-truyen-item-wrap, "
            "div.list-comic-item-wrap"
        )

        candidates = []
        seen_slugs = set()

        for element in soup.select(
            selectors
        ):
            anchor = (
                element.select_one(
                    "h3 a[href]"
                )
                or element.select_one(
                    "a[href*='/manga/']"
                )
            )

            if anchor is None:
                continue

            absolute_url = urljoin(
                cls.BASE_URL,
                anchor.get(
                    "href",
                    "",
                ),
            )

            slug = cls.extract_title_id(
                absolute_url
            )

            title = anchor.get_text(
                " ",
                strip=True,
            )

            if (
                not slug
                or not title
                or slug in seen_slugs
            ):
                continue

            image = element.select_one(
                "img"
            )

            thumbnail_url = None

            if image is not None:
                raw_thumbnail = (
                    image.get("src")
                    or image.get("data-src")
                    or ""
                )

                if raw_thumbnail:
                    thumbnail_url = urljoin(
                        cls.BASE_URL,
                        raw_thumbnail,
                    )

            candidates.append(
                MangabatCandidate(
                    source_id=slug,
                    title=title,
                    url=(
                        cls.build_series_url(
                            slug
                        )
                    ),
                    thumbnail_url=(
                        thumbnail_url
                        or None
                    ),
                )
            )

            seen_slugs.add(slug)

        return candidates

    def fetch_candidate(
        self,
        slug,
    ):
        series_url = (
            self.build_series_url(
                slug
            )
        )

        response = self._get(
            series_url
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        info_element = (
            soup.select_one(
                "div.manga-info-top"
            )
            or soup.select_one(
                "div.panel-story-info"
            )
        )

        title_element = (
            info_element.select_one(
                "h1, h2"
            )
            if info_element
            else None
        )

        if title_element is None:
            title_element = (
                soup.select_one("h1")
                or soup.select_one("h2")
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
            return None

        image = (
            soup.select_one(
                "div.manga-info-pic img"
            )
            or soup.select_one(
                "span.info-image img"
            )
        )

        thumbnail_url = None

        if image is not None:
            raw_thumbnail = (
                image.get("src")
                or image.get("data-src")
                or ""
            )

            if raw_thumbnail:
                thumbnail_url = urljoin(
                    self.BASE_URL,
                    raw_thumbnail,
                )

        return MangabatCandidate(
            source_id=slug,
            title=title,
            url=series_url,
            thumbnail_url=(
                thumbnail_url
                or None
            ),
        )

    def fetch_chapters(
        self,
        series_url,
    ):
        slug = self.extract_title_id(
            series_url
        )

        if not slug:
            raise ValueError(
                "Invalid Mangabat "
                "series URL or slug."
            )

        api_url = (
            f"{self.BASE_URL}/api/"
            f"manga/{slug}/chapters"
        )

        response = self._get(
            api_url,
            params={
                "limit": -1,
            },
        )

        try:
            payload = response.json()

        except ValueError as error:
            raise RuntimeError(
                "Mangabat returned an "
                "invalid chapter response."
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise RuntimeError(
                "Mangabat returned an "
                "unexpected chapter response."
            )

        if not payload.get(
            "success",
            False,
        ):
            return []

        data = payload.get(
            "data",
            {},
        )

        chapter_values = (
            data.get(
                "chapters",
                [],
            )
            if isinstance(
                data,
                dict,
            )
            else []
        )

        chapters = []
        seen_slugs = set()

        for chapter_data in (
            chapter_values
        ):
            chapter = (
                self._chapter_from_data(
                    chapter_data,
                    manga_slug=slug,
                )
            )

            if (
                chapter is None
                or chapter.source_id
                in seen_slugs
            ):
                continue

            chapters.append(
                chapter
            )
            seen_slugs.add(
                chapter.source_id
            )

        return chapters

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
                or datetime.min.replace(
                    tzinfo=timezone.utc
                ),
            ),
        )

    @classmethod
    def _chapter_from_data(
        cls,
        chapter_data,
        *,
        manga_slug,
    ):
        if not isinstance(
            chapter_data,
            dict,
        ):
            return None

        chapter_slug = str(
            chapter_data.get(
                "chapter_slug",
                "",
            )
        ).strip()

        chapter_number = (
            cls.parse_chapter_number(
                chapter_data.get(
                    "chapter_num"
                )
            )
        )

        if (
            not chapter_slug
            or chapter_number is None
        ):
            return None

        label = str(
            chapter_data.get(
                "chapter_name",
                "",
            )
        ).strip()

        if not label:
            label = (
                f"Chapter "
                f"{chapter_number}"
            )

        return MangabatChapter(
            source_id=chapter_slug,
            label=label,
            number=chapter_number,
            url=cls.build_chapter_url(
                manga_slug,
                chapter_slug,
            ),
            published_at=(
                cls.parse_datetime(
                    chapter_data.get(
                        "updated_at"
                    )
                )
            ),
        )

    @staticmethod
    def parse_chapter_number(
        value,
    ):
        if value in {
            None,
            "",
        }:
            return None

        try:
            return Decimal(
                str(value).strip()
            )

        except (
            InvalidOperation,
            ValueError,
        ):
            return None

    @staticmethod
    def parse_datetime(
        value,
    ):
        if not value:
            return None

        clean_value = str(
            value
        ).strip()

        if not clean_value:
            return None

        try:
            parsed = (
                datetime.fromisoformat(
                    clean_value.replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed
