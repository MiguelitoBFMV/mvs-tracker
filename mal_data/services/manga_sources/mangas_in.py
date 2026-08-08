import re
import time

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse

import requests

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class MangasInCandidate:
    source_id: str
    title: str
    url: str
    thumbnail_url: str | None = None


@dataclass(frozen=True)
class MangasInChapter:
    source_id: str
    label: str
    number: Decimal
    url: str
    published_at: datetime | None = None


class MangasInClient:
    BASE_URL = "https://m440.in"
    SEARCH_URL = f"{BASE_URL}/search"

    REQUEST_INTERVAL_SECONDS = 1.05
    REQUEST_TIMEOUT_SECONDS = 30

    ACCEPTED_HOSTS = {
        "m440.in",
        "www.m440.in",
        "mangas.in",
        "www.mangas.in",
    }

    def __init__(self, session=None):
        self.session = session or requests.Session()
        self._last_request_at = None

        self.session.headers.update(
            {
                "Accept": (
                    "text/html,"
                    "application/json;q=0.9,"
                    "*/*;q=0.8"
                ),
                "Accept-Language": (
                    "es-CL,es;q=0.9,"
                    "en;q=0.8"
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

        elapsed = time.monotonic() - self._last_request_at
        remaining = self.REQUEST_INTERVAL_SECONDS - elapsed

        if remaining > 0:
            time.sleep(remaining)

    def _get(self, url, *, params=None):
        self._wait_for_rate_limit()

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
        finally:
            self._last_request_at = time.monotonic()

        if response.status_code == 429:
            raise RuntimeError(
                "Mangas.in rate limit reached "
                "(HTTP 429)."
            )

        if response.status_code == 403:
            raise RuntimeError(
                "Mangas.in rejected the request "
                "(HTTP 403)."
            )

        response.raise_for_status()
        return response

    @classmethod
    def build_series_url(cls, slug):
        return f"{cls.BASE_URL}/manga/{slug}"

    @classmethod
    def build_thumbnail_url(cls, slug):
        return (
            f"{cls.BASE_URL}/uploads/manga/"
            f"{slug}/cover/cover_250x350.jpg"
        )

    @classmethod
    def extract_title_id(cls, value):
        clean_value = str(value).strip()

        if not clean_value:
            return None

        parsed = urlparse(clean_value)

        if parsed.scheme:
            if parsed.netloc not in cls.ACCEPTED_HOSTS:
                return None

            parts = [
                part
                for part in parsed.path.split("/")
                if part
            ]

            if len(parts) >= 2 and parts[0] == "manga":
                return parts[1]

            return None

        if (
            "/" not in clean_value
            and " " not in clean_value
            and re.fullmatch(
                r"[a-z0-9][a-z0-9-]*",
                clean_value,
                re.IGNORECASE,
            )
        ):
            return clean_value

        return None

    def search(self, query):
        clean_query = " ".join(
            str(query).strip().split()
        )

        if not clean_query:
            return []

        direct_slug = self.extract_title_id(clean_query)

        if direct_slug:
            candidate = self.fetch_candidate(direct_slug)
            return [candidate] if candidate else []

        response = self._get(
            self.SEARCH_URL,
            params={"q": clean_query},
        )

        try:
            payload = response.json()
        except ValueError as error:
            raise RuntimeError(
                "Mangas.in returned an invalid "
                "search response."
            ) from error

        if not isinstance(payload, list):
            raise RuntimeError(
                "Mangas.in returned an unexpected "
                "search response."
            )

        candidates = []
        seen_slugs = set()

        for item in payload:
            if not isinstance(item, dict):
                continue

            title = str(item.get("value", "")).strip()
            slug = (
                str(item.get("data", ""))
                .strip()
                .strip("/")
            )

            if not title or not slug or slug in seen_slugs:
                continue

            candidates.append(
                MangasInCandidate(
                    source_id=slug,
                    title=title,
                    url=self.build_series_url(slug),
                    thumbnail_url=(
                        self.build_thumbnail_url(slug)
                    ),
                )
            )
            seen_slugs.add(slug)

        return candidates

    def fetch_candidate(self, slug):
        series_url = self.build_series_url(slug)
        response = self._get(series_url)

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        title_element = (
            soup.select_one("div.manga-name h1")
            or soup.select_one(".listmanga-header")
            or soup.select_one(".widget-title")
            or soup.select_one("h1")
            or soup.select_one("h2")
        )

        title = (
            title_element.get_text(" ", strip=True)
            if title_element
            else ""
        )

        if not title:
            return None

        return MangasInCandidate(
            source_id=slug,
            title=title,
            url=series_url,
            thumbnail_url=self.build_thumbnail_url(slug),
        )

    def fetch_chapters(self, series_url):
        slug = self.extract_title_id(series_url)

        if not slug:
            raise ValueError(
                "Invalid Mangas.in series URL or slug."
            )

        canonical_url = self.build_series_url(slug)
        response = self._get(canonical_url)

        return self.parse_series_html(
            response.text,
            series_url=canonical_url,
        )

    def fetch_latest_chapter(self, series_url):
        chapters = self.fetch_chapters(series_url)

        if not chapters:
            return None

        return max(
            chapters,
            key=lambda chapter: (
                chapter.number,
                chapter.source_id,
            ),
        )

    @classmethod
    def parse_series_html(cls, html, *, series_url):
        soup = BeautifulSoup(html, "html.parser")
        slug = cls.extract_title_id(series_url)
        expected_prefix = f"/manga/{slug}/"

        chapters = []
        seen_values = set()

        for anchor in soup.find_all("a", href=True):
            label = anchor.get_text(" ", strip=True)
            chapter_number = cls.parse_chapter_number(label)

            if chapter_number is None:
                continue

            chapter_url = urljoin(
                series_url,
                anchor.get("href", ""),
            )
            parsed = urlparse(chapter_url)

            if parsed.netloc not in cls.ACCEPTED_HOSTS:
                continue

            if not parsed.path.startswith(expected_prefix):
                continue

            source_id = (
                parsed.path.rstrip("/").split("/")[-1]
            )
            dedupe_key = (source_id, chapter_number)

            if not source_id or dedupe_key in seen_values:
                continue

            chapters.append(
                MangasInChapter(
                    source_id=source_id,
                    label=label,
                    number=chapter_number,
                    url=chapter_url,
                    published_at=None,
                )
            )
            seen_values.add(dedupe_key)

        return chapters

    @staticmethod
    def parse_chapter_number(label):
        if not label:
            return None

        match = re.search(
            (
                r"(?:cap[ií]tulo|cap\.?|ch\.?|chapter|#)"
                r"\s*"
                r"([0-9]+(?:\.[0-9]+)?)"
            ),
            str(label),
            re.IGNORECASE,
        )

        if not match:
            return None

        try:
            return Decimal(match.group(1))
        except InvalidOperation:
            return None
