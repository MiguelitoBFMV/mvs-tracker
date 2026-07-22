from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from mal_data.models import (
    AnimeEntry,
    AnimeSyncEvent,
    MALOAuthToken,
    ManualTrackedAnime,
)
from mal_data.services.anime_list_sync import (
    sync_anime_status,
)
from mal_data.services.episode_signal_sync import (
    get_active_signal_entries,
    sync_episode_signals_complete,
)
from mal_data.services.mal_client import (
    MyAnimeListClient,
)
from mal_data.services.mal_oauth import (
    exchange_authorization_code,
    get_valid_access_token,
)
from mal_data.services.manual_tracked_sync import (
    sync_manual_tracked_anime_entry,
)


def build_anime_item(
    *,
    mal_id=100,
    title="Test Anime",
    status="watching",
    episodes_watched=1,
    score=0,
    is_rewatching=False,
):
    return {
        "node": {
            "id": mal_id,
            "title": title,
            "main_picture": {
                "medium": (
                    "https://example.com/medium.jpg"
                ),
                "large": (
                    "https://example.com/large.jpg"
                ),
            },
            "alternative_titles": {
                "ja": "テストアニメ",
                "en": "Test Anime",
            },
            "media_type": "tv",
            "status": "currently_airing",
            "num_episodes": 12,
            "start_date": "2026-07-01",
            "end_date": None,
        },
        "list_status": {
            "status": status,
            "score": score,
            "num_episodes_watched": episodes_watched,
            "is_rewatching": is_rewatching,
            "updated_at": (
                "2026-07-22T12:00:00+00:00"
            ),
        },
    }


def create_anime_entry(
    *,
    mal_id,
    title,
    list_status="watching",
    episodes_watched=0,
    is_rewatching=False,
):
    return AnimeEntry.objects.create(
        mal_id=mal_id,
        title=title,
        list_status=list_status,
        num_episodes_watched=episodes_watched,
        is_rewatching=is_rewatching,
        num_episodes=12,
        airing_status="currently_airing",
    )


class FakeAnimeListClient:
    def __init__(self, entries):
        self.entries = entries

    def fetch_all_anime_by_status(self, status):
        yield {
            "page": 1,
            "entries": self.entries,
            "total_accumulated": len(self.entries),
        }


class MalInsightsPublicRouteTests(TestCase):
    def get_public_urls(self):
        return [
            reverse("mal_insights:dashboard"),
            reverse(
                "mal_insights:anime_status_list",
                kwargs={"status": "watching"},
            ),
            reverse(
                "mal_insights:anime_relations_detail",
                kwargs={"mal_id": 999999},
            ),
            reverse("mal_insights:anime_search"),
            reverse("mal_insights:seasonal_board"),
        ]

    def test_public_routes_are_available_without_login(
        self,
    ):
        for url in self.get_public_urls():
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    200,
                )


class MalInsightsProtectedRouteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects
            .create_user(
                username="test-owner",
            )
        )

    def get_protected_post_urls(self):
        return [
            reverse("mal_insights:sync_anime_list"),
            reverse("mal_insights:sync_mal_library"),
            reverse(
                "mal_insights:sync_episode_signals"
            ),
            reverse(
                "mal_insights:sync_manual_rescues"
            ),
            reverse(
                "mal_insights:sync_anime_relations",
                kwargs={"mal_id": 999999},
            ),
            reverse(
                "mal_insights:rescue_anime_from_search"
            ),
            reverse(
                "mal_insights:sync_seasonal_board"
            ),
            reverse(
                "mal_insights:add_seasonal_to_plan"
            ),
        ]

    def test_anonymous_get_requests_redirect_to_login(
        self,
    ):
        login_url = reverse("login")

        for url in self.get_protected_post_urls():
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    302,
                )

                self.assertTrue(
                    response.url.startswith(
                        f"{login_url}?next="
                    )
                )

    def test_anonymous_post_requests_redirect_to_login(
        self,
    ):
        login_url = reverse("login")

        for url in self.get_protected_post_urls():
            with self.subTest(url=url):
                response = self.client.post(url)

                self.assertEqual(
                    response.status_code,
                    302,
                )

                self.assertTrue(
                    response.url.startswith(
                        f"{login_url}?next="
                    )
                )

    def test_authenticated_get_requests_return_405(
        self,
    ):
        self.client.force_login(self.owner)

        for url in self.get_protected_post_urls():
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    405,
                )


class MALOAuthServiceTests(TestCase):
    def build_token_response(
        self,
        *,
        access_token="new-access-token",
        refresh_token="new-refresh-token",
    ):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.content = b'{"access_token":"token"}'
        response.text = ""

        response.json.return_value = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        return response

    @patch(
        "mal_data.services.mal_oauth.requests.post"
    )
    def test_authorization_exchange_saves_tokens(
        self,
        mock_post,
    ):
        mock_post.return_value = (
            self.build_token_response()
        )

        token = exchange_authorization_code(
            code="authorization-code",
            code_verifier="test-code-verifier",
        )

        self.assertEqual(
            token.access_token,
            "new-access-token",
        )

        self.assertEqual(
            token.refresh_token,
            "new-refresh-token",
        )

        self.assertTrue(
            token.expires_at > timezone.now()
        )

        self.assertEqual(
            MALOAuthToken.objects.count(),
            1,
        )

        request_data = (
            mock_post.call_args.kwargs["data"]
        )

        self.assertEqual(
            request_data["grant_type"],
            "authorization_code",
        )

        self.assertEqual(
            request_data["code"],
            "authorization-code",
        )

        self.assertEqual(
            request_data["code_verifier"],
            "test-code-verifier",
        )

    @patch(
        "mal_data.services.mal_oauth.requests.post"
    )
    def test_expired_token_is_refreshed_and_saved(
        self,
        mock_post,
    ):
        stored_token = MALOAuthToken.objects.create(
            pk=1,
            access_token="expired-access-token",
            refresh_token="old-refresh-token",
            token_type="Bearer",
            expires_at=(
                timezone.now()
                - timedelta(minutes=1)
            ),
        )

        mock_post.return_value = (
            self.build_token_response(
                access_token="refreshed-access-token",
                refresh_token="rotated-refresh-token",
            )
        )

        access_token = get_valid_access_token()

        self.assertEqual(
            access_token,
            "refreshed-access-token",
        )

        stored_token.refresh_from_db()

        self.assertEqual(
            stored_token.access_token,
            "refreshed-access-token",
        )

        self.assertEqual(
            stored_token.refresh_token,
            "rotated-refresh-token",
        )

        self.assertTrue(
            stored_token.expires_at > timezone.now()
        )


class MyAnimeListClientTests(TestCase):
    @patch(
        "mal_data.services.mal_client.requests.request"
    )
    @patch(
        (
            "mal_data.services.mal_client."
            "get_valid_access_token"
        )
    )
    def test_401_refreshes_and_retries_once(
        self,
        mock_get_token,
        mock_request,
    ):
        unauthorized_response = Mock()
        unauthorized_response.status_code = 401
        unauthorized_response.ok = False
        unauthorized_response.content = (
            b'{"error":"invalid_token"}'
        )
        unauthorized_response.text = (
            '{"error":"invalid_token"}'
        )

        success_response = Mock()
        success_response.status_code = 200
        success_response.ok = True
        success_response.content = b'{"ok":true}'
        success_response.text = '{"ok":true}'
        success_response.json.return_value = {
            "ok": True,
        }

        mock_get_token.side_effect = [
            "expired-token",
            "fresh-token",
        ]

        mock_request.side_effect = [
            unauthorized_response,
            success_response,
        ]

        client = MyAnimeListClient()

        result = client.fetch_page(
            "https://example.test/anime"
        )

        self.assertEqual(
            result,
            {"ok": True},
        )

        self.assertEqual(
            mock_request.call_count,
            2,
        )

        self.assertEqual(
            mock_get_token.call_count,
            2,
        )

        self.assertFalse(
            mock_get_token.call_args_list[
                0
            ].kwargs["force_refresh"]
        )

        self.assertTrue(
            mock_get_token.call_args_list[
                1
            ].kwargs["force_refresh"]
        )


class MALAnimeLibrarySyncTests(TestCase):
    def test_create_unchanged_and_update_paths(
        self,
    ):
        initial_item = build_anime_item(
            episodes_watched=1,
        )

        first_result = sync_anime_status(
            "watching",
            save_raw=False,
            client=FakeAnimeListClient(
                [initial_item]
            ),
        )

        self.assertEqual(
            first_result["created"],
            1,
        )

        self.assertEqual(
            first_result["updated"],
            0,
        )

        self.assertEqual(
            first_result["unchanged"],
            0,
        )

        second_result = sync_anime_status(
            "watching",
            save_raw=False,
            client=FakeAnimeListClient(
                [initial_item]
            ),
        )

        self.assertEqual(
            second_result["created"],
            0,
        )

        self.assertEqual(
            second_result["updated"],
            0,
        )

        self.assertEqual(
            second_result["unchanged"],
            1,
        )

        changed_item = build_anime_item(
            episodes_watched=2,
        )

        third_result = sync_anime_status(
            "watching",
            save_raw=False,
            client=FakeAnimeListClient(
                [changed_item]
            ),
        )

        self.assertEqual(
            third_result["created"],
            0,
        )

        self.assertEqual(
            third_result["updated"],
            1,
        )

        self.assertEqual(
            third_result["unchanged"],
            0,
        )

        anime = AnimeEntry.objects.get(mal_id=100)

        self.assertEqual(
            anime.num_episodes_watched,
            2,
        )

        self.assertTrue(
            AnimeSyncEvent.objects.filter(
                anime=anime,
                event_type="episode_changed",
                old_value="EP. 1",
                new_value="EP. 2",
            ).exists()
        )


class EpisodeSignalSyncTests(TestCase):
    def test_target_selection_only_includes_active_entries(
        self,
    ):
        watching = create_anime_entry(
            mal_id=101,
            title="Watching",
            list_status="watching",
        )

        rewatching = create_anime_entry(
            mal_id=102,
            title="Rewatching",
            list_status="completed",
            is_rewatching=True,
        )

        rescued = create_anime_entry(
            mal_id=103,
            title="Manual Rescue",
            list_status="watching",
        )

        ManualTrackedAnime.objects.create(
            mal_id=rescued.mal_id,
            title_snapshot=rescued.title,
            status="watching",
            active=True,
        )

        create_anime_entry(
            mal_id=104,
            title="Completed",
            list_status="completed",
        )

        create_anime_entry(
            mal_id=105,
            title="Plan",
            list_status="plan_to_watch",
        )

        target_ids = set(
            get_active_signal_entries()
            .values_list(
                "mal_id",
                flat=True,
            )
        )

        self.assertEqual(
            target_ids,
            {
                watching.mal_id,
                rewatching.mal_id,
                rescued.mal_id,
            },
        )

    @patch(
        (
            "mal_data.services.episode_signal_sync."
            "sync_airing_data_for_anime"
        )
    )
    @patch(
        (
            "mal_data.services.episode_signal_sync."
            "MyAnimeListClient"
        )
    )
    def test_complete_sync_updates_progress_tracker_and_log(
        self,
        mock_client_class,
        mock_sync_airing,
    ):
        anime = create_anime_entry(
            mal_id=200,
            title="Active Anime",
            list_status="watching",
            episodes_watched=2,
        )

        tracker = ManualTrackedAnime.objects.create(
            mal_id=anime.mal_id,
            title_snapshot=anime.title,
            status="watching",
            episodes_watched=2,
            active=True,
        )

        mal_client = Mock()

        mal_client.fetch_anime_my_list_status.return_value = {
            "status": "watching",
            "score": 0,
            "num_episodes_watched": 3,
            "is_rewatching": False,
            "updated_at": (
                "2026-07-22T16:00:00+00:00"
            ),
        }

        mock_client_class.return_value = mal_client

        mock_sync_airing.return_value = (
            SimpleNamespace(
                pending_episodes_for_user=0
            ),
            False,
        )

        results = sync_episode_signals_complete()

        anime.refresh_from_db()
        tracker.refresh_from_db()

        self.assertEqual(
            anime.num_episodes_watched,
            3,
        )

        self.assertEqual(
            tracker.episodes_watched,
            3,
        )

        self.assertTrue(
            results["personal"][0]["changed"]
        )

        self.assertTrue(
            AnimeSyncEvent.objects.filter(
                anime=anime,
                event_type="episode_changed",
                old_value="EP. 2",
                new_value="EP. 3",
            ).exists()
        )

        mock_sync_airing.assert_called_once_with(
            anime.mal_id
        )


class ManualTrackedAnimeSyncTests(TestCase):
    @patch(
        (
            "mal_data.services.manual_tracked_sync."
            "MyAnimeListClient"
        )
    )
    def test_manual_sync_uses_real_mal_progress(
        self,
        mock_client_class,
    ):
        anime = create_anime_entry(
            mal_id=300,
            title="Rescued Anime",
            list_status="watching",
            episodes_watched=1,
        )

        tracker = ManualTrackedAnime.objects.create(
            mal_id=anime.mal_id,
            title_snapshot=anime.title,
            status="watching",
            episodes_watched=1,
            active=True,
        )

        mal_client = Mock()

        mal_client.fetch_anime_details.return_value = {
            "id": anime.mal_id,
            "title": anime.title,
            "main_picture": {},
            "alternative_titles": {},
            "media_type": "tv",
            "status": "currently_airing",
            "num_episodes": 12,
            "start_date": "2026-07-01",
            "end_date": None,
        }

        mal_client.fetch_anime_my_list_status.return_value = {
            "status": "watching",
            "score": 0,
            "num_episodes_watched": 2,
            "is_rewatching": False,
            "updated_at": (
                "2026-07-22T16:00:00+00:00"
            ),
        }

        mock_client_class.return_value = mal_client

        synced_anime, created = (
            sync_manual_tracked_anime_entry(
                tracker
            )
        )

        synced_anime.refresh_from_db()
        tracker.refresh_from_db()

        self.assertFalse(created)

        self.assertEqual(
            synced_anime.num_episodes_watched,
            2,
        )

        self.assertEqual(
            tracker.episodes_watched,
            2,
        )

        self.assertTrue(
            AnimeSyncEvent.objects.filter(
                anime=synced_anime,
                event_type="episode_changed",
                old_value="EP. 1",
                new_value="EP. 2",
            ).exists()
        )