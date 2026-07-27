import requests

from django.conf import settings


TMDB_API_BASE_URL = (
    "https://api.themoviedb.org/3"
)
TMDB_TIMEOUT_SECONDS = 15
TMDB_MAX_SEARCH_RESULTS = 20


class TMDBClientError(Exception):
    """Base exception for TMDB integration."""


class TMDBConfigurationError(
    TMDBClientError
):
    """Raised when TMDB is not configured."""


class TMDBAuthenticationError(
    TMDBClientError
):
    """Raised when TMDB rejects the token."""


class TMDBNotFoundError(
    TMDBClientError
):
    """Raised when a TMDB object is missing."""


class TMDBRateLimitError(
    TMDBClientError
):
    """Raised when TMDB rate limits requests."""


class TMDBRequestError(
    TMDBClientError
):
    """Raised when a TMDB request fails."""


class TMDBClient:
    def __init__(
        self,
        *,
        access_token=None,
        language=None,
        region=None,
    ):
        if access_token is None:
            access_token = getattr(
                settings,
                "TMDB_READ_ACCESS_TOKEN",
                None,
            )

        if language is None:
            language = getattr(
                settings,
                "TMDB_LANGUAGE",
                "en-US",
            )

        if region is None:
            region = getattr(
                settings,
                "TMDB_REGION",
                "CL",
            )

        self.access_token = access_token
        self.language = language
        self.region = region

        if not self.access_token:
            raise TMDBConfigurationError(
                (
                    "TMDB Read Access Token "
                    "is not configured."
                )
            )

    def request(
        self,
        endpoint,
        *,
        params=None,
    ):
        request_params = {
            "language": self.language,
        }

        for key, value in (
            params or {}
        ).items():
            if value is not None:
                request_params[key] = value

        url = (
            f"{TMDB_API_BASE_URL}/"
            f"{endpoint.lstrip('/')}"
        )

        try:
            response = requests.get(
                url,
                headers={
                    "Accept": (
                        "application/json"
                    ),
                    "Authorization": (
                        "Bearer "
                        f"{self.access_token}"
                    ),
                },
                params=request_params,
                timeout=TMDB_TIMEOUT_SECONDS,
            )
        except requests.Timeout as error:
            raise TMDBRequestError(
                "TMDB request timed out."
            ) from error
        except requests.RequestException as error:
            raise TMDBRequestError(
                "Could not connect to TMDB."
            ) from error

        if response.status_code in {
            401,
            403,
        }:
            raise TMDBAuthenticationError(
                (
                    "TMDB rejected the configured "
                    "Read Access Token."
                )
            )

        if response.status_code == 404:
            raise TMDBNotFoundError(
                "The requested TMDB item was not found."
            )

        if response.status_code == 429:
            raise TMDBRateLimitError(
                (
                    "TMDB rate limit reached. "
                    "Try again in a moment."
                )
            )

        if response.status_code >= 400:
            response_preview = (
                response.text[:300]
            )

            raise TMDBRequestError(
                (
                    "TMDB request failed with "
                    f"status "
                    f"{response.status_code}: "
                    f"{response_preview}"
                )
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise TMDBRequestError(
                (
                    "TMDB returned an invalid "
                    "JSON response."
                )
            ) from error

        if not isinstance(payload, dict):
            raise TMDBRequestError(
                (
                    "TMDB returned an unexpected "
                    "response."
                )
            )

        return payload

    def _validate_tmdb_id(
        self,
        tmdb_id,
        *,
        label,
    ):
        try:
            tmdb_id = int(tmdb_id)
        except (
            TypeError,
            ValueError,
        ) as error:
            raise TMDBRequestError(
                f"{label} must be numeric."
            ) from error

        if tmdb_id <= 0:
            raise TMDBRequestError(
                f"{label} must be positive."
            )

        return tmdb_id

    def _validate_page(self, page):
        try:
            page = int(page)
        except (
            TypeError,
            ValueError,
        ) as error:
            raise TMDBRequestError(
                (
                    "TMDB search page must "
                    "be numeric."
                )
            ) from error

        return max(page, 1)

    def _validate_limit(self, limit):
        try:
            limit = int(limit)
        except (
            TypeError,
            ValueError,
        ) as error:
            raise TMDBRequestError(
                (
                    "TMDB search limit must "
                    "be numeric."
                )
            ) from error

        return max(
            1,
            min(
                limit,
                TMDB_MAX_SEARCH_RESULTS,
            ),
        )

    def _search(
        self,
        endpoint,
        query,
        *,
        page=1,
        limit=10,
        include_region=False,
    ):
        query = str(
            query or ""
        ).strip()

        if not query:
            return []

        safe_page = self._validate_page(
            page
        )
        safe_limit = self._validate_limit(
            limit
        )

        params = {
            "query": query,
            "page": safe_page,
            "include_adult": "false",
        }

        if (
            include_region
            and self.region
        ):
            params["region"] = self.region

        payload = self.request(
            endpoint,
            params=params,
        )

        results = payload.get("results")

        if not isinstance(results, list):
            raise TMDBRequestError(
                (
                    "TMDB search returned an "
                    "unexpected result list."
                )
            )

        valid_results = [
            item
            for item in results
            if isinstance(item, dict)
        ]

        return valid_results[
            :safe_limit
        ]

    def search_movie(
        self,
        query,
        *,
        page=1,
        limit=10,
    ):
        return self._search(
            "search/movie",
            query,
            page=page,
            limit=limit,
            include_region=True,
        )

    def search_series(
        self,
        query,
        *,
        page=1,
        limit=10,
    ):
        return self._search(
            "search/tv",
            query,
            page=page,
            limit=limit,
        )

    def get_movie(self, tmdb_id):
        tmdb_id = self._validate_tmdb_id(
            tmdb_id,
            label="TMDB movie ID",
        )

        return self.request(
            f"movie/{tmdb_id}"
        )

    def get_collection(
        self,
        collection_id,
    ):
        collection_id = (
            self._validate_tmdb_id(
                collection_id,
                label=(
                    "TMDB collection ID"
                ),
            )
        )

        return self.request(
            f"collection/{collection_id}"
        )

    def get_series(self, tmdb_id):
        tmdb_id = self._validate_tmdb_id(
            tmdb_id,
            label="TMDB series ID",
        )

        return self.request(
            f"tv/{tmdb_id}"
        )

    def get_series_season(
        self,
        tmdb_id,
        season_number,
    ):
        tmdb_id = self._validate_tmdb_id(
            tmdb_id,
            label="TMDB series ID",
        )

        try:
            season_number = int(
                season_number
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise TMDBRequestError(
                (
                    "TMDB season number must "
                    "be numeric."
                )
            ) from error

        if season_number < 0:
            raise TMDBRequestError(
                (
                    "TMDB season number cannot "
                    "be negative."
                )
            )

        return self.request(
            (
                f"tv/{tmdb_id}/season/"
                f"{season_number}"
            )
        )


