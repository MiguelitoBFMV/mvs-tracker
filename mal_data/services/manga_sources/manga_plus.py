import os
import re

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from mangaplus import MangaPlus
from mangaplus.constants import Language


@dataclass(frozen=True)
class MangaPlusCandidate:
    source_id: str
    title: str
    url: str
    thumbnail_url: str | None = None


@dataclass(frozen=True)
class MangaPlusChapter:
    source_id: str
    label: str
    number: Decimal
    url: str
    published_at: datetime | None = None


class MangaPlusClient:
    BASE_URL = (
        "https://mangaplus.shueisha.co.jp"
    )

    def __init__(self, api_client=None):
        self.api_client = (
            api_client
            or MangaPlus(
                lang=Language.ENGLISH,
            )
        )

        self._registered = (
            api_client is not None
        )

    def _ensure_registered(self):
        if self._registered:
            return

        stored_secret = os.getenv(
            "MANGAPLUS_DEVICE_SECRET",
            "",
        ).strip()

        if stored_secret:
            self.api_client.secret = (
                stored_secret
            )
            self._registered = True
            return

        device_id = os.getenv(
            "MANGAPLUS_DEVICE_ID",
            "",
        ).strip()

        if not device_id:
            raise RuntimeError(
                "MANGAPLUS_DEVICE_ID is not "
                "configured in .env."
            )

        result = self.api_client.register(
            device_id=device_id
        )

        registration_data = result.get(
            "registerationData",
            {},
        )

        secret = registration_data.get(
            "deviceSecret",
            "",
        )

        if not secret:
            raise RuntimeError(
                "MANGA Plus registration did "
                "not return a device secret."
            )

        self._registered = True

    @classmethod
    def build_title_url(cls, title_id):
        return (
            f"{cls.BASE_URL}/titles/"
            f"{title_id}"
        )

    @classmethod
    def build_chapter_url(
        cls,
        chapter_id,
    ):
        return (
            f"{cls.BASE_URL}/viewer/"
            f"{chapter_id}"
        )

    @classmethod
    def extract_title_id(cls, value):
        clean_value = str(value).strip()

        if clean_value.isdigit():
            return clean_value

        parsed = urlparse(clean_value)

        if parsed.netloc not in {
            "mangaplus.shueisha.co.jp",
            "www.mangaplus.shueisha.co.jp",
        }:
            return None

        parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        if (
            len(parts) >= 2
            and parts[0] == "titles"
            and parts[1].isdigit()
        ):
            return parts[1]

        return None

    def fetch_title_detail(
        self,
        title_id,
    ):
        self._ensure_registered()

        response = (
            self.api_client.getTitleDetail(
                title_id=int(title_id)
            )
        )

        detail = response.get(
            "titleDetailView"
        )

        if not detail:
            raise RuntimeError(
                "MANGA Plus returned no "
                "title detail."
            )

        return detail

    def search(self, query):
        clean_query = " ".join(
            str(query).strip().split()
        )

        if not clean_query:
            return []

        title_id = self.extract_title_id(
            clean_query
        )

        if title_id:
            detail = self.fetch_title_detail(
                title_id
            )

            candidate = (
                self._candidate_from_detail(
                    detail,
                    title_id,
                )
            )

            return (
                [candidate]
                if candidate
                else []
            )

        self._ensure_registered()

        response = (
            self.api_client.getSearchTitles()
        )

        candidates = []
        seen_ids = set()

        for title_data in (
            self._walk_title_dicts(response)
        ):
            candidate = (
                self._candidate_from_title(
                    title_data
                )
            )

            if (
                candidate is None
                or candidate.source_id
                in seen_ids
            ):
                continue

            candidates.append(candidate)
            seen_ids.add(
                candidate.source_id
            )

        return candidates

    @classmethod
    def _walk_title_dicts(
        cls,
        value,
    ):
        if isinstance(value, dict):
            if (
                "titleId" in value
                and "name" in value
            ):
                yield value

            for child in value.values():
                yield from (
                    cls._walk_title_dicts(
                        child
                    )
                )

        elif isinstance(value, list):
            for child in value:
                yield from (
                    cls._walk_title_dicts(
                        child
                    )
                )

    @classmethod
    def _candidate_from_title(
        cls,
        title_data,
    ):
        title_id = str(
            title_data.get(
                "titleId",
                "",
            )
        ).strip()

        title = str(
            title_data.get(
                "name",
                "",
            )
        ).strip()

        if (
            not title_id.isdigit()
            or not title
        ):
            return None

        return MangaPlusCandidate(
            source_id=title_id,
            title=title,
            url=cls.build_title_url(
                title_id
            ),
            thumbnail_url=(
                title_data.get(
                    "portraitImageUrl"
                )
                or None
            ),
        )

    @classmethod
    def _candidate_from_detail(
        cls,
        detail,
        title_id,
    ):
        title_data = detail.get(
            "title",
            {},
        )

        if not title_data:
            return None

        title_data = {
            **title_data,
            "titleId": (
                title_data.get(
                    "titleId"
                )
                or title_id
            ),
        }

        return cls._candidate_from_title(
            title_data
        )

    def fetch_chapters(
        self,
        series_url,
    ):
        title_id = self.extract_title_id(
            series_url
        )

        if not title_id:
            raise ValueError(
                "Invalid MANGA Plus "
                "title URL."
            )

        detail = self.fetch_title_detail(
            title_id
        )

        chapter_dicts = []

        for key in (
            "chapterListV2",
            "firstChapterList",
            "lastChapterList",
        ):
            chapter_dicts.extend(
                detail.get(key, [])
            )

        for group in detail.get(
            "chapterListGroup",
            [],
        ):
            for key in (
                "firstChapterList",
                "midChapterList",
                "lastChapterList",
            ):
                chapter_dicts.extend(
                    group.get(key, [])
                )

        chapters = []
        seen_ids = set()

        for chapter_data in chapter_dicts:
            chapter = (
                self._chapter_from_dict(
                    chapter_data
                )
            )

            if (
                chapter is None
                or chapter.source_id
                in seen_ids
            ):
                continue

            chapters.append(chapter)
            seen_ids.add(
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
    def _chapter_from_dict(
        cls,
        chapter_data,
    ):
        chapter_id = str(
            chapter_data.get(
                "chapterId",
                "",
            )
        ).strip()

        label = (
            str(
                chapter_data.get(
                    "name",
                    "",
                )
            ).strip()
            or str(
                chapter_data.get(
                    "subTitle",
                    "",
                )
            ).strip()
        )

        chapter_number = (
            cls.parse_chapter_number(
                label
            )
        )

        if (
            not chapter_id.isdigit()
            or chapter_number is None
        ):
            return None

        published_at = None

        raw_timestamp = (
            chapter_data.get(
                "startTimeStamp"
            )
        )

        if raw_timestamp is not None:
            try:
                published_at = (
                    datetime.fromtimestamp(
                        int(raw_timestamp),
                        tz=timezone.utc,
                    )
                )

            except (
                TypeError,
                ValueError,
                OverflowError,
            ):
                published_at = None

        return MangaPlusChapter(
            source_id=chapter_id,
            label=label,
            number=chapter_number,
            url=cls.build_chapter_url(
                chapter_id
            ),
            published_at=published_at,
        )

    @staticmethod
    def parse_chapter_number(label):
        if not label:
            return None

        match = re.search(
            (
                r"(?:chapter|ch\.?|#)"
                r"\s*"
                r"([0-9]+(?:\.[0-9]+)?)"
            ),
            str(label),
            re.IGNORECASE,
        )

        if match:
            raw_number = match.group(1)

        else:
            numbers = re.findall(
                r"[0-9]+(?:\.[0-9]+)?",
                str(label),
            )

            if not numbers:
                return None

            raw_number = numbers[-1]

        try:
            return Decimal(raw_number)

        except InvalidOperation:
            return None

