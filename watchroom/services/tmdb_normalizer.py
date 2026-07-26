from datetime import date

from watchroom.models import MediaWork


TMDB_IMAGE_BASE_URL = (
    "https://image.tmdb.org/t/p"
)
TMDB_POSTER_SIZE = "w500"
TMDB_BACKDROP_SIZE = "original"

TMDB_ANIMATION_GENRE_ID = 16
TMDB_DOCUMENTARY_GENRE_ID = 99


class TMDBNormalizationError(
    ValueError
):
    """Raised for unusable TMDB payloads."""


def build_tmdb_image_url(
    file_path,
    *,
    size,
):
    if not file_path:
        return ""

    file_path = str(file_path)

    if not file_path.startswith("/"):
        file_path = f"/{file_path}"

    return (
        f"{TMDB_IMAGE_BASE_URL}/"
        f"{size}"
        f"{file_path}"
    )


def parse_tmdb_date(value):
    if not value:
        return None

    try:
        return date.fromisoformat(
            str(value)
        )
    except ValueError:
        return None


def _required_tmdb_id(payload):
    try:
        tmdb_id = int(
            payload.get("id")
        )
    except (
        AttributeError,
        TypeError,
        ValueError,
    ) as error:
        raise TMDBNormalizationError(
            (
                "TMDB payload does not contain "
                "a usable ID."
            )
        ) from error

    if tmdb_id <= 0:
        raise TMDBNormalizationError(
            "TMDB ID must be positive."
        )

    return tmdb_id


def _positive_integer_or_none(value):
    try:
        value = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if value <= 0:
        return None

    return value


def _non_negative_integer(value):
    try:
        value = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0

    return max(value, 0)


def _genre_ids(payload):
    genre_ids = set()

    for genre_id in (
        payload.get("genre_ids") or []
    ):
        try:
            genre_ids.add(
                int(genre_id)
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

    for genre in (
        payload.get("genres") or []
    ):
        if not isinstance(genre, dict):
            continue

        try:
            genre_ids.add(
                int(genre.get("id"))
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

    return genre_ids


def infer_presentation(payload):
    genre_ids = _genre_ids(payload)

    if (
        TMDB_ANIMATION_GENRE_ID
        in genre_ids
    ):
        return (
            MediaWork.Presentation.ANIMATION
        )

    if (
        TMDB_DOCUMENTARY_GENRE_ID
        in genre_ids
    ):
        return (
            MediaWork.Presentation.DOCUMENTARY
        )

    return (
        MediaWork.Presentation.LIVE_ACTION
    )


def _genre_names(payload):
    names = []

    for genre in (
        payload.get("genres") or []
    ):
        if not isinstance(genre, dict):
            continue

        name = str(
            genre.get("name") or ""
        ).strip()

        if name and name not in names:
            names.append(name)

    return names


def _country_codes(items):
    codes = []

    for item in items or []:
        if isinstance(item, dict):
            code = item.get(
                "iso_3166_1"
            )
        else:
            code = item

        code = str(
            code or ""
        ).strip().upper()

        if code and code not in codes:
            codes.append(code)

    return codes


def _network_names(payload):
    names = []

    for network in (
        payload.get("networks") or []
    ):
        if not isinstance(
            network,
            dict,
        ):
            continue

        name = str(
            network.get("name") or ""
        ).strip()

        if name and name not in names:
            names.append(name)

    return names


def _display_title(
    payload,
    *,
    title_key,
    original_title_key,
    fallback,
):
    title = str(
        payload.get(title_key) or ""
    ).strip()
    original_title = str(
        payload.get(
            original_title_key
        )
        or ""
    ).strip()

    return (
        title
        or original_title
        or fallback
    )


def normalize_movie_search_result(
    payload,
):
    tmdb_id = _required_tmdb_id(
        payload
    )

    return {
        "tmdb_id": tmdb_id,
        "media_type": (
            MediaWork.MediaType.MOVIE
        ),
        "title": _display_title(
            payload,
            title_key="title",
            original_title_key=(
                "original_title"
            ),
            fallback=(
                f"TMDB Movie {tmdb_id}"
            ),
        ),
        "original_title": str(
            payload.get(
                "original_title"
            )
            or ""
        ).strip(),
        "overview": str(
            payload.get("overview") or ""
        ).strip(),
        "original_language": str(
            payload.get(
                "original_language"
            )
            or ""
        ).strip(),
        "first_release_date": (
            parse_tmdb_date(
                payload.get(
                    "release_date"
                )
            )
        ),
        "presentation": (
            infer_presentation(payload)
        ),
        "poster_url": (
            build_tmdb_image_url(
                payload.get(
                    "poster_path"
                ),
                size=TMDB_POSTER_SIZE,
            )
        ),
        "backdrop_url": (
            build_tmdb_image_url(
                payload.get(
                    "backdrop_path"
                ),
                size=(
                    TMDB_BACKDROP_SIZE
                ),
            )
        ),
        "popularity": (
            payload.get("popularity")
        ),
        "vote_average": (
            payload.get("vote_average")
        ),
        "tmdb_payload": dict(payload),
    }


def normalize_series_search_result(
    payload,
):
    tmdb_id = _required_tmdb_id(
        payload
    )

    return {
        "tmdb_id": tmdb_id,
        "media_type": (
            MediaWork.MediaType.SERIES
        ),
        "title": _display_title(
            payload,
            title_key="name",
            original_title_key=(
                "original_name"
            ),
            fallback=(
                f"TMDB Series {tmdb_id}"
            ),
        ),
        "original_title": str(
            payload.get(
                "original_name"
            )
            or ""
        ).strip(),
        "overview": str(
            payload.get("overview") or ""
        ).strip(),
        "original_language": str(
            payload.get(
                "original_language"
            )
            or ""
        ).strip(),
        "first_release_date": (
            parse_tmdb_date(
                payload.get(
                    "first_air_date"
                )
            )
        ),
        "presentation": (
            infer_presentation(payload)
        ),
        "origin_countries": (
            _country_codes(
                payload.get(
                    "origin_country"
                )
            )
        ),
        "poster_url": (
            build_tmdb_image_url(
                payload.get(
                    "poster_path"
                ),
                size=TMDB_POSTER_SIZE,
            )
        ),
        "backdrop_url": (
            build_tmdb_image_url(
                payload.get(
                    "backdrop_path"
                ),
                size=(
                    TMDB_BACKDROP_SIZE
                ),
            )
        ),
        "popularity": (
            payload.get("popularity")
        ),
        "vote_average": (
            payload.get("vote_average")
        ),
        "tmdb_payload": dict(payload),
    }


def normalize_movie_details(payload):
    normalized = (
        normalize_movie_search_result(
            payload
        )
    )

    normalized.update(
        {
            "runtime_minutes": (
                _positive_integer_or_none(
                    payload.get("runtime")
                )
            ),
            "external_status": str(
                payload.get("status") or ""
            ).strip(),
            "genres": (
                _genre_names(payload)
            ),
            "origin_countries": (
                _country_codes(
                    payload.get(
                        "production_countries"
                    )
                )
            ),
            "networks": [],
        }
    )

    return normalized


def normalize_season_summary(payload):
    tmdb_id = _required_tmdb_id(
        payload
    )

    return {
        "tmdb_id": tmdb_id,
        "season_number": (
            _non_negative_integer(
                payload.get(
                    "season_number"
                )
            )
        ),
        "name": str(
            payload.get("name") or ""
        ).strip(),
        "episode_count": (
            _non_negative_integer(
                payload.get(
                    "episode_count"
                )
            )
        ),
        "air_date": (
            parse_tmdb_date(
                payload.get("air_date")
            )
        ),
        "poster_url": (
            build_tmdb_image_url(
                payload.get(
                    "poster_path"
                ),
                size=TMDB_POSTER_SIZE,
            )
        ),
        "tmdb_payload": dict(payload),
    }


def normalize_series_details(payload):
    normalized = (
        normalize_series_search_result(
            payload
        )
    )

    seasons = []

    for season_payload in (
        payload.get("seasons") or []
    ):
        if not isinstance(
            season_payload,
            dict,
        ):
            continue

        try:
            seasons.append(
                normalize_season_summary(
                    season_payload
                )
            )
        except TMDBNormalizationError:
            continue

    normalized.update(
        {
            "runtime_minutes": None,
            "external_status": str(
                payload.get("status") or ""
            ).strip(),
            "genres": (
                _genre_names(payload)
            ),
            "origin_countries": (
                _country_codes(
                    payload.get(
                        "origin_country"
                    )
                )
            ),
            "networks": (
                _network_names(payload)
            ),
            "seasons": seasons,
        }
    )

    return normalized


def normalize_season_details(payload):
    normalized = (
        normalize_season_summary(
            payload
        )
    )

    episodes = payload.get(
        "episodes"
    )

    if isinstance(episodes, list):
        normalized[
            "episode_count"
        ] = len(episodes)

    return normalized


