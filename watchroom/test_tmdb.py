from unittest.mock import (
    Mock,
    patch,
)

import requests

from django.test import (
    SimpleTestCase,
    override_settings,
)

from watchroom.models import MediaWork
from watchroom.services.tmdb_client import (
    TMDBAuthenticationError,
    TMDBClient,
    TMDBConfigurationError,
    TMDBNotFoundError,
    TMDBRateLimitError,
    TMDBRequestError,
)
from watchroom.services.tmdb_normalizer import (
    TMDBNormalizationError,
    normalize_movie_details,
    normalize_movie_search_result,
    normalize_season_details,
    normalize_series_details,
    normalize_series_search_result,
)


def build_mock_response(
    *,
    status_code=200,
    payload=None,
    text="",
):
    response = Mock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = (
        payload
        if payload is not None
        else {}
    )

    return response


class TMDBClientTests(SimpleTestCase):
    @override_settings(
        TMDB_READ_ACCESS_TOKEN=None
    )
    def test_missing_token_is_rejected(
        self,
    ):
        with self.assertRaises(
            TMDBConfigurationError
        ):
            TMDBClient()

    @patch(
        "watchroom.services."
        "tmdb_client.requests.get"
    )
    def test_request_uses_bearer_token(
        self,
        mock_get,
    ):
        mock_get.return_value = (
            build_mock_response(
                payload={
                    "id": 11,
                },
            )
        )

        client = TMDBClient(
            access_token="tmdb-token",
            language="en-US",
            region="CL",
        )

        result = client.request(
            "movie/11"
        )

        self.assertEqual(
            result["id"],
            11,
        )

        _args, kwargs = (
            mock_get.call_args
        )

        self.assertEqual(
            kwargs["headers"][
                "Authorization"
            ],
            "Bearer tmdb-token",
        )
        self.assertEqual(
            kwargs["params"][
                "language"
            ],
            "en-US",
        )

    @patch(
        "watchroom.services."
        "tmdb_client.requests.get"
    )
    def test_movie_search_uses_region(
        self,
        mock_get,
    ):
        mock_get.return_value = (
            build_mock_response(
                payload={
                    "results": [
                        {
                            "id": 1,
                        },
                        {
                            "id": 2,
                        },
                        {
                            "id": 3,
                        },
                    ],
                },
            )
        )

        client = TMDBClient(
            access_token="tmdb-token",
            region="CL",
        )

        results = client.search_movie(
            "Saw",
            limit=2,
        )

        self.assertEqual(
            len(results),
            2,
        )

        _args, kwargs = (
            mock_get.call_args
        )

        self.assertEqual(
            kwargs["params"]["query"],
            "Saw",
        )
        self.assertEqual(
            kwargs["params"]["region"],
            "CL",
        )
        self.assertEqual(
            kwargs["params"][
                "include_adult"
            ],
            "false",
        )

    @patch(
        "watchroom.services."
        "tmdb_client.requests.get"
    )
    def test_series_search_uses_tv_endpoint(
        self,
        mock_get,
    ):
        mock_get.return_value = (
            build_mock_response(
                payload={
                    "results": [
                        {
                            "id": 1,
                        },
                    ],
                },
            )
        )

        client = TMDBClient(
            access_token="tmdb-token",
            region="CL",
        )

        client.search_series(
            "Phineas and Ferb"
        )

        args, kwargs = (
            mock_get.call_args
        )

        self.assertEqual(
            args[0],
            (
                "https://api."
                "themoviedb.org/3/"
                "search/tv"
            ),
        )
        self.assertNotIn(
            "region",
            kwargs["params"],
        )

    @patch(
        "watchroom.services."
        "tmdb_client.requests.get"
    )
    def test_authentication_error(
        self,
        mock_get,
    ):
        mock_get.return_value = (
            build_mock_response(
                status_code=401,
            )
        )

        client = TMDBClient(
            access_token="bad-token"
        )

        with self.assertRaises(
            TMDBAuthenticationError
        ):
            client.get_movie(11)

    @patch(
        "watchroom.services."
        "tmdb_client.requests.get"
    )
    def test_not_found_error(
        self,
        mock_get,
    ):
        mock_get.return_value = (
            build_mock_response(
                status_code=404,
            )
        )

        client = TMDBClient(
            access_token="tmdb-token"
        )

        with self.assertRaises(
            TMDBNotFoundError
        ):
            client.get_series(999)

    @patch(
        "watchroom.services."
        "tmdb_client.requests.get"
    )
    def test_rate_limit_error(
        self,
        mock_get,
    ):
        mock_get.return_value = (
            build_mock_response(
                status_code=429,
            )
        )

        client = TMDBClient(
            access_token="tmdb-token"
        )

        with self.assertRaises(
            TMDBRateLimitError
        ):
            client.search_movie("Saw")

    @patch(
        "watchroom.services."
        "tmdb_client.requests.get"
    )
    def test_invalid_json_is_rejected(
        self,
        mock_get,
    ):
        response = build_mock_response()
        response.json.side_effect = (
            ValueError
        )
        mock_get.return_value = response

        client = TMDBClient(
            access_token="tmdb-token"
        )

        with self.assertRaises(
            TMDBRequestError
        ):
            client.get_movie(11)

    @patch(
        "watchroom.services."
        "tmdb_client.requests.get"
    )
    def test_unexpected_search_payload(
        self,
        mock_get,
    ):
        mock_get.return_value = (
            build_mock_response(
                payload={
                    "results": {},
                },
            )
        )

        client = TMDBClient(
            access_token="tmdb-token"
        )

        with self.assertRaises(
            TMDBRequestError
        ):
            client.search_series("Gumball")

    @patch(
        "watchroom.services."
        "tmdb_client.requests.get"
    )
    def test_timeout_is_translated(
        self,
        mock_get,
    ):
        mock_get.side_effect = (
            requests.Timeout
        )

        client = TMDBClient(
            access_token="tmdb-token"
        )

        with self.assertRaises(
            TMDBRequestError
        ):
            client.get_movie(11)


class TMDBNormalizerTests(
    SimpleTestCase
):
    def test_movie_search_result(
        self,
    ):
        result = (
            normalize_movie_search_result(
                {
                    "id": 12,
                    "title": "Example Movie",
                    "original_title": (
                        "Original Movie"
                    ),
                    "overview": "Overview",
                    "original_language": "en",
                    "release_date": (
                        "2026-07-25"
                    ),
                    "genre_ids": [16],
                    "poster_path": (
                        "/poster.jpg"
                    ),
                    "backdrop_path": (
                        "/backdrop.jpg"
                    ),
                }
            )
        )

        self.assertEqual(
            result["media_type"],
            MediaWork.MediaType.MOVIE,
        )
        self.assertEqual(
            result["presentation"],
            (
                MediaWork.Presentation
                .ANIMATION
            ),
        )
        self.assertEqual(
            result[
                "first_release_date"
            ].isoformat(),
            "2026-07-25",
        )
        self.assertEqual(
            result["poster_url"],
            (
                "https://image.tmdb.org/"
                "t/p/w500/poster.jpg"
            ),
        )

    def test_series_search_result(
        self,
    ):
        result = (
            normalize_series_search_result(
                {
                    "id": 21,
                    "name": (
                        "Phineas and Ferb"
                    ),
                    "original_name": (
                        "Phineas and Ferb"
                    ),
                    "origin_country": [
                        "US",
                    ],
                    "first_air_date": (
                        "2007-08-17"
                    ),
                    "genre_ids": [16],
                }
            )
        )

        self.assertEqual(
            result["media_type"],
            MediaWork.MediaType.SERIES,
        )
        self.assertEqual(
            result[
                "origin_countries"
            ],
            [
                "US",
            ],
        )

    def test_movie_details(self):
        result = normalize_movie_details(
            {
                "id": 30,
                "title": "Documentary",
                "original_title": (
                    "Documentary"
                ),
                "genres": [
                    {
                        "id": 99,
                        "name": (
                            "Documentary"
                        ),
                    },
                ],
                "runtime": 95,
                "status": "Released",
                "production_countries": [
                    {
                        "iso_3166_1": "CL",
                    },
                ],
            }
        )

        self.assertEqual(
            result["runtime_minutes"],
            95,
        )
        self.assertEqual(
            result["external_status"],
            "Released",
        )
        self.assertEqual(
            result["presentation"],
            (
                MediaWork.Presentation
                .DOCUMENTARY
            ),
        )
        self.assertEqual(
            result["origin_countries"],
            [
                "CL",
            ],
        )

    def test_series_details(self):
        result = normalize_series_details(
            {
                "id": 40,
                "name": "Example Series",
                "original_name": (
                    "Example Series"
                ),
                "status": (
                    "Returning Series"
                ),
                "genres": [
                    {
                        "id": 18,
                        "name": "Drama",
                    },
                ],
                "origin_country": [
                    "US",
                ],
                "networks": [
                    {
                        "name": "Disney",
                    },
                ],
                "seasons": [
                    {
                        "id": 401,
                        "season_number": 0,
                        "name": "Specials",
                        "episode_count": 4,
                    },
                    {
                        "id": 402,
                        "season_number": 1,
                        "name": "Season 1",
                        "episode_count": 38,
                    },
                ],
            }
        )

        self.assertIsNone(
            result["runtime_minutes"]
        )
        self.assertEqual(
            result["networks"],
            [
                "Disney",
            ],
        )
        self.assertEqual(
            len(result["seasons"]),
            2,
        )
        self.assertEqual(
            result["seasons"][0][
                "season_number"
            ],
            0,
        )

    def test_season_details_use_episode_list(
        self,
    ):
        result = normalize_season_details(
            {
                "id": 501,
                "season_number": 1,
                "name": "Season 1",
                "episode_count": 99,
                "episodes": [
                    {
                        "id": 1,
                    },
                    {
                        "id": 2,
                    },
                    {
                        "id": 3,
                    },
                ],
            }
        )

        self.assertEqual(
            result["episode_count"],
            3,
        )

    def test_missing_id_is_rejected(
        self,
    ):
        with self.assertRaises(
            TMDBNormalizationError
        ):
            normalize_movie_details(
                {
                    "title": "Missing ID",
                }
            )


