import base64
import threading
import time

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse

import requests


@dataclass(frozen=True)
class MangaFireCandidate:
    source_id: str
    title: str
    url: str
    thumbnail_url: str | None = None


@dataclass(frozen=True)
class MangaFireChapter:
    source_id: str
    label: str
    number: Decimal
    url: str
    published_at: datetime | None = None


class MangaFireVrfSigner:
    _TABLES = (
        (
            "yINlmUNho8VYJT+ibTIP+9ESiULpVEtMOoD6U6lRE0R/xwXo/Xp9NrUgC4cw/"
            "Lmo33vUyjUE40kUoEWIr/fxfNNcq2s79ShQ5NhNrFnJ4hXPwOu/SuXzIbuTQK"
            "GFvfm08E9jvCfqAtoDqvQq3dVWPQFmJjgvkISBeXY3BgANR+yVnjGbcxZ47d6"
            "kLNfZPIayTq3/YGySb1KuVZodWp/WGNAO5pfMcpaK53Hhs0allBszaMaxuouOwd"
            "xbwgxIw6YunSsXjI05Yi0j9j4eHKfSXR8Ifo/Od+8iamRfCXTyvm7NGRGYdcQ0"
            "ywcK/u6RXhrbcCm4t2eCtrDgQVecJGkQ+A==",
            "0Ec58JOY3uBzJK9m3zqIOpdlF7UFiax9DmA=",
            0x5A,
        ),
        (
            "IUFltCxD3Oc2cwCgkJffthaOg9cgPUb0LgW6H/VtfcF0kc5F25t+aWj6JH9VO"
            "hOaY0rAFdUxlDnl5BLNvwEJvQtP5qcw7vdb/K+chnbwnspSHT8mz5lqwz41Tez"
            "G0hkO06FTjJZhsyNuFLDpD2ZZxQj/QIRcF90zpmQ7Byu483WsQqUE0C342HL+JX"
            "ngRB6fRzxRyVTaKu83h7UYTJ0QMt6ixFh6S3F8gqkKwrGTL3jHNBsD45UnifK8"
            "+RGtishQV2K3rujLKEkiZxpr2dYcudFW4oFsDKhad3CLBvuyTqsCo4B7mL5IKQ"
            "1vXo/MOOvq1I1d8ar9X6Ttu5KF4fZgiA==",
            "AAdjb1iPY8CiDmq9H34tKTBF8a3oDQ==",
            0x35,
        ),
        (
            "NQHlu1/wVO5EmkwQymF810qqY2xG1k2obcas4Z9mCsPEIFl9pRIjFxbJ7ybMHb"
            "BckT5Ton85E0FOeHezbh/mjlEYpmpnlXOS8dgrqeq2KfxImTh1YK9y0PeMNhzA"
            "1OQzSY9brYOJq/l2QnE/hwOeZIhPixVSKIUlDb5vLcH6RWKxkIEMuP0bDwIqQ7"
            "1AJJaEaMJL7A6YtyIwoRT+L5v4aZzodN/0+3nOGsfblFjgxSfPzVDjNFeNl5P2"
            "6+kEC/8AHgdrpAbt3hHz3HrRN1Y6e+JHgF7ncFWnoF0y3THL1S71WgWGCa6KtS"
            "zTCCG58n68nTyj2T3Sshk7utqCtMi/ZQ==",
            "DELOJgPsVaCcblDtTGMdHzM=",
            0xBA,
        ),
    )

    @classmethod
    def sign(cls, value):
        data = str(value).encode("utf-8")

        for encoded_table, encoded_key, iv in cls._TABLES:
            table = base64.b64decode(encoded_table)
            key = base64.b64decode(encoded_key)

            output = bytearray(len(data))
            previous = iv

            for index, byte in enumerate(data):
                previous = table[
                    (
                        byte
                        ^ key[index % len(key)]
                        ^ previous
                    )
                    & 0xFF
                ]
                output[index] = previous

            data = bytes(output)

        return (
            base64.urlsafe_b64encode(data)
            .decode("ascii")
            .rstrip("=")
        )

    @classmethod
    def sign_api_request(
        cls,
        url,
        params=None,
    ):
        parsed = urlparse(url)

        if not parsed.path.startswith("/api/"):
            return params

        flattened = []

        for key, value in (
            params or {}
        ).items():
            values = (
                value
                if isinstance(
                    value,
                    (list, tuple),
                )
                else [value]
            )

            for item in values:
                flattened.append(
                    (
                        str(key),
                        str(item),
                    )
                )

        flattened.sort(
            key=lambda item: item[0]
        )

        indexed_counts = {}
        signing_parts = []

        for key, value in flattened:
            signing_key = key

            if key.endswith("[]"):
                index = indexed_counts.get(
                    key,
                    0,
                )
                indexed_counts[key] = (
                    index + 1
                )
                signing_key = (
                    f"{key[:-2]}[{index}]"
                )

            signing_parts.append(
                f"{signing_key}={value}"
            )

        signing_value = (
            parsed.path.removeprefix(
                "/api"
            )
        )

        if signing_parts:
            signing_value += (
                "?"
                + "&".join(
                    signing_parts
                )
            )

        signed_params = list(
            flattened
        )
        signed_params.append(
            (
                "vrf",
                cls.sign(signing_value),
            )
        )

        return signed_params


class MangaFireClient:
    BASE_URL = "https://mangafire.to"
    TITLES_API_URL = f"{BASE_URL}/api/titles"

    REQUEST_INTERVAL_SECONDS = 1.05
    REQUEST_TIMEOUT_SECONDS = 30
    SEARCH_LIMIT = 30

    _request_lock = threading.Lock()
    _last_request_started_at = None
    CHAPTER_PAGE_LIMIT = 200
    MAX_CHAPTER_PAGES = 100

    def __init__(self, session=None):
        self.session = (
            session
            or requests.Session()
        )
        self._enforce_rate_limit = (
            session is None
        )

        self.session.headers.update(
            {
                "Accept": (
                    "application/json,"
                    "text/plain;q=0.9,"
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

    @classmethod
    def _wait_for_rate_limit(cls):
        with cls._request_lock:
            if (
                cls._last_request_started_at
                is not None
            ):
                elapsed = (
                    time.monotonic()
                    - cls._last_request_started_at
                )

                remaining = (
                    cls.REQUEST_INTERVAL_SECONDS
                    - elapsed
                )

                if remaining > 0:
                    time.sleep(remaining)

            cls._last_request_started_at = (
                time.monotonic()
            )

    def _get_json(
        self,
        url,
        *,
        params=None,
    ):
        if self._enforce_rate_limit:
            self._wait_for_rate_limit()

        signed_params = (
            MangaFireVrfSigner
            .sign_api_request(
                url,
                params=params,
            )
        )

        response = self.session.get(
            url,
            params=signed_params,
            timeout=(
                self.REQUEST_TIMEOUT_SECONDS
            ),
        )

        if response.status_code == 403:
            raw_body = getattr(
                response,
                "text",
                "",
            )

            response_details = (
                " ".join(
                    raw_body.split()
                )[:180]
                if isinstance(
                    raw_body,
                    str,
                )
                else ""
            )

            message = (
                "MangaFire rejected the "
                "request (HTTP 403). This "
                "can be a temporary provider "
                "or IP block."
            )

            if response_details:
                message = (
                    f"{message} Response: "
                    f"{response_details}"
                )

            raise RuntimeError(message)

        if response.status_code == 429:
            raise RuntimeError(
                "MangaFire rate limit "
                "reached (HTTP 429)."
            )

        response.raise_for_status()

        try:
            payload = response.json()

        except ValueError as error:
            raise RuntimeError(
                "MangaFire returned an "
                "invalid JSON response."
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise RuntimeError(
                "MangaFire returned an "
                "unexpected API response."
            )

        return payload

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

        if not parsed.scheme:
            if (
                "/" not in clean_value
                and "." not in clean_value
                and "-" not in clean_value
                and clean_value.isalnum()
                and any(
                    character.isdigit()
                    for character
                    in clean_value
                )
            ):
                return clean_value

            return None

        if parsed.netloc not in {
            "mangafire.to",
            "www.mangafire.to",
        }:
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
            and parts[0] == "title"
        ):
            title_part = parts[1]
            title_id = title_part.split(
                "-",
                1,
            )[0].strip()

            return (
                title_id
                if title_id
                else None
            )

        if (
            len(parts) >= 2
            and parts[0] == "manga"
            and "." in parts[1]
        ):
            _slug, title_id = (
                parts[1].rsplit(
                    ".",
                    1,
                )
            )

            title_id = title_id.strip()

            return (
                title_id
                if title_id
                else None
            )

        return None

    @classmethod
    def build_title_url(
        cls,
        title_id,
    ):
        return (
            f"{cls.BASE_URL}/title/"
            f"{title_id}"
        )

    @staticmethod
    def _poster_url(
        poster,
    ):
        if isinstance(
            poster,
            dict,
        ):
            return (
                poster.get("medium")
                or poster.get("large")
                or poster.get("small")
                or None
            )

        if isinstance(
            poster,
            str,
        ):
            return poster or None

        return None

    @classmethod
    def _candidate_from_title_data(
        cls,
        title_data,
        *,
        fallback_id=None,
    ):
        if not isinstance(
            title_data,
            dict,
        ):
            return None

        raw_url = str(
            title_data.get(
                "url",
                "",
            )
        ).strip()

        absolute_url = (
            urljoin(
                cls.BASE_URL,
                raw_url,
            )
            if raw_url
            else ""
        )

        source_id = (
            str(
                title_data.get(
                    "id",
                    "",
                )
            ).strip()
            or cls.extract_title_id(
                absolute_url
            )
            or str(
                fallback_id
                or ""
            ).strip()
        )

        title = str(
            title_data.get(
                "title",
                "",
            )
        ).strip()

        if (
            not source_id
            or not title
        ):
            return None

        if not absolute_url:
            absolute_url = (
                cls.build_title_url(
                    source_id
                )
            )

        thumbnail_url = (
            cls._poster_url(
                title_data.get(
                    "poster"
                )
            )
        )

        if thumbnail_url:
            thumbnail_url = urljoin(
                cls.BASE_URL,
                thumbnail_url,
            )

        return MangaFireCandidate(
            source_id=source_id,
            title=title,
            url=absolute_url,
            thumbnail_url=(
                thumbnail_url
                or None
            ),
        )

    def fetch_title_detail(
        self,
        title_id,
    ):
        payload = self._get_json(
            (
                f"{self.TITLES_API_URL}/"
                f"{title_id}"
            )
        )

        detail = payload.get(
            "data"
        )

        if not isinstance(
            detail,
            dict,
        ):
            raise RuntimeError(
                "MangaFire returned no "
                "title detail."
            )

        return detail

    def search(
        self,
        query,
    ):
        clean_query = " ".join(
            str(query).strip().split()
        )

        if not clean_query:
            return []

        title_id = self.extract_title_id(
            clean_query
        )

        if title_id:
            detail = (
                self.fetch_title_detail(
                    title_id
                )
            )

            candidate = (
                self
                ._candidate_from_title_data(
                    detail,
                    fallback_id=title_id,
                )
            )

            return (
                [candidate]
                if candidate
                else []
            )

        payload = self._get_json(
            self.TITLES_API_URL,
            params={
                "keyword": clean_query,
                "language": "en",
                "limit": (
                    self.SEARCH_LIMIT
                ),
                "page": 1,
            },
        )

        candidates = []
        seen_ids = set()

        for title_data in (
            payload.get("items", [])
        ):
            candidate = (
                self
                ._candidate_from_title_data(
                    title_data
                )
            )

            if (
                candidate is None
                or candidate.source_id
                in seen_ids
            ):
                continue

            candidates.append(
                candidate
            )
            seen_ids.add(
                candidate.source_id
            )

        return candidates

    @staticmethod
    def parse_chapter_number(
        value,
    ):
        if value is None:
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
        if value in {
            None,
            "",
        }:
            return None

        if isinstance(
            value,
            (
                int,
                float,
                Decimal,
            ),
        ):
            try:
                return (
                    datetime.fromtimestamp(
                        float(value),
                        tz=timezone.utc,
                    )
                )

            except (
                ValueError,
                OverflowError,
                OSError,
            ):
                return None

        clean_value = str(
            value
        ).strip()

        if not clean_value:
            return None

        try:
            numeric_value = float(
                clean_value
            )

        except ValueError:
            numeric_value = None

        if numeric_value is not None:
            try:
                return (
                    datetime.fromtimestamp(
                        numeric_value,
                        tz=timezone.utc,
                    )
                )

            except (
                ValueError,
                OverflowError,
                OSError,
            ):
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

    @classmethod
    def _chapter_from_data(
        cls,
        chapter_data,
        *,
        series_url,
    ):
        if not isinstance(
            chapter_data,
            dict,
        ):
            return None

        source_id = str(
            chapter_data.get(
                "id",
                "",
            )
        ).strip()

        chapter_number = (
            cls.parse_chapter_number(
                chapter_data.get(
                    "number"
                )
            )
        )

        if (
            not source_id
            or chapter_number is None
        ):
            return None

        chapter_name = str(
            chapter_data.get(
                "name",
                "",
            )
        ).strip()

        label = (
            f"Chapter {chapter_number}"
        )

        if chapter_name:
            label = (
                f"{label}: "
                f"{chapter_name}"
            )

        raw_url = str(
            chapter_data.get(
                "url",
                "",
            )
        ).strip()

        chapter_url = (
            urljoin(
                cls.BASE_URL,
                raw_url,
            )
            if raw_url
            else (
                f"{series_url.rstrip('/')}"
                f"/chapter/{source_id}"
            )
        )

        return MangaFireChapter(
            source_id=source_id,
            label=label,
            number=chapter_number,
            url=chapter_url,
            published_at=(
                cls.parse_datetime(
                    chapter_data.get(
                        "createdAt"
                    )
                )
            ),
        )

    def fetch_chapters(
        self,
        series_url,
    ):
        title_id = (
            self.extract_title_id(
                series_url
            )
        )

        if not title_id:
            raise ValueError(
                "Invalid MangaFire "
                "title URL or ID."
            )

        canonical_series_url = (
            str(series_url).strip()
        )

        if not urlparse(
            canonical_series_url
        ).scheme:
            canonical_series_url = (
                self.build_title_url(
                    title_id
                )
            )

        api_url = (
            f"{self.TITLES_API_URL}/"
            f"{title_id}/chapters"
        )

        chapters = []
        seen_ids = set()
        page = 1

        while (
            page
            <= self.MAX_CHAPTER_PAGES
        ):
            payload = self._get_json(
                api_url,
                params={
                    "language": "en",
                    "sort": "number",
                    "order": "desc",
                    "limit": (
                        self
                        .CHAPTER_PAGE_LIMIT
                    ),
                    "page": page,
                },
            )

            for chapter_data in (
                payload.get(
                    "items",
                    [],
                )
            ):
                chapter = (
                    self
                    ._chapter_from_data(
                        chapter_data,
                        series_url=(
                            canonical_series_url
                        ),
                    )
                )

                if (
                    chapter is None
                    or chapter.source_id
                    in seen_ids
                ):
                    continue

                chapters.append(
                    chapter
                )
                seen_ids.add(
                    chapter.source_id
                )

            meta = payload.get(
                "meta",
                {},
            )

            if not (
                isinstance(meta, dict)
                and meta.get(
                    "hasNext"
                )
            ):
                break

            page += 1

        else:
            raise RuntimeError(
                "MangaFire chapter "
                "pagination exceeded the "
                "configured safety limit."
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
