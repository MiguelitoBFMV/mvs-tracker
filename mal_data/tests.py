from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import (
    SimpleTestCase,
    TestCase,
)
from django.urls import reverse
from django.utils import timezone
from django.core.management import (
    call_command,
)
from django.core.management.base import (
    CommandError,
)

from mal_data.models import (
    AnimeEntry,
    AnimeSyncEvent,
    MALOAuthToken,
    MangaChapterSignal,
    MangaEntry,
    MangaSourceLink,
    MangaSyncEvent,
    ManualTrackedAnime,
    ManualTrackedManga,
)
from mal_data.services.anime_list_sync import (
    sync_anime_status,
)
from mal_data.services.manga_list_sync import (
    sync_manga_status,
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
from mal_data.services.manga_reading_sync import (
    get_active_reading_entries,
    sync_reading_progress,
)
from mal_data.services.manga_chapter_signal_sync import (
    get_actionable_chapter_signals,
    sync_canonical_chapter_signals,
)
from mal_data.services.manga_source_matching import (
    source_title_score,
)
from mal_data.services.manga_sources.weeb_central import (
    WeebCentralClient,
)
from mal_data.services.manga_source_signal_sync import (
    sync_all_external_chapter_signals,
    sync_external_chapter_signal,
)
from mal_data.services.manga_sources.manga_plus import (
    MangaPlusClient,
)
from mal_data.services.manga_source_resolver import (
    MangaSourceFetchError,
    fetch_latest_saved_chapter,
)
from mal_data.services.manga_source_search import (
    get_candidate_by_source_id,
    save_manga_source_candidate,
    search_manga_sources,
    save_manga_source_candidate_with_role
)
from mal_data.services.manga_source_management import (
    make_manga_source_primary,
    toggle_manga_source_active,
    unlink_manga_source,
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


def build_manga_item(
    *,
    mal_id=200,
    title="Test Manga",
    status="reading",
    chapters_read=1,
    volumes_read=0,
    score=0,
    is_rereading=False,
):
    return {
        "node": {
            "id": mal_id,
            "title": title,
            "main_picture": {
                "medium": (
                    "https://example.com/"
                    "manga-medium.jpg"
                ),
                "large": (
                    "https://example.com/"
                    "manga-large.jpg"
                ),
            },
            "alternative_titles": {
                "ja": "テストマンガ",
                "en": "Test Manga",
            },
            "media_type": "manga",
            "status": "currently_publishing",
            "num_volumes": 10,
            "num_chapters": 100,
            "start_date": "2026-01-01",
            "end_date": None,
        },
        "list_status": {
            "status": status,
            "score": score,
            "num_volumes_read": volumes_read,
            "num_chapters_read": chapters_read,
            "is_rereading": is_rereading,
            "updated_at": (
                "2026-07-27T12:00:00+00:00"
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


class FakeMangaListClient:
    def __init__(self, entries):
        self.entries = entries

    def fetch_all_manga_by_status(
        self,
        status,
    ):
        yield {
            "page": 1,
            "entries": self.entries,
            "total_accumulated": len(
                self.entries
            ),
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
            reverse(
                "manga_insights:sync_manga_library"
            ),
            reverse(
                "manga_insights:"
                "sync_reading_progress"
            ),
            reverse(
                "manga_insights:"
                "sync_manual_manga_rescues"
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


class MangaInsightsFoundationTests(TestCase):
    def test_manga_dashboard_is_public_and_displays_metrics(
        self,
    ):
        MangaEntry.objects.create(
            mal_id=1001,
            title="Reading Manga",
            list_status="reading",
            num_chapters_read=12,
            num_volumes_read=2,
            is_rereading=True,
        )

        MangaEntry.objects.create(
            mal_id=1002,
            title="Completed Manga",
            list_status="completed",
            num_chapters_read=50,
            num_volumes_read=8,
        )

        response = self.client.get(
            reverse("manga_insights:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.context["total_manga"],
            2,
        )
        self.assertEqual(
            response.context["reading_count"],
            1,
        )
        self.assertEqual(
            response.context["rereading_count"],
            1,
        )
        self.assertEqual(
            response.context["completed_count"],
            1,
        )
        self.assertEqual(
            response.context["chapters_read"],
            62,
        )
        self.assertEqual(
            response.context["volumes_read"],
            10,
        )

    def test_anime_and_manga_pages_show_world_switch(
        self,
    ):
        anime_url = reverse(
            "mal_insights:dashboard"
        )
        manga_url = reverse(
            "manga_insights:dashboard"
        )

        for url in (anime_url, manga_url):
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    200,
                )
                self.assertContains(
                    response,
                    f'href="{anime_url}"',
                )
                self.assertContains(
                    response,
                    f'href="{manga_url}"',
                )


class MALMangaLibrarySyncTests(TestCase):
    def test_create_unchanged_and_update_paths(
        self,
    ):
        initial_item = build_manga_item(
            chapters_read=1,
        )

        first_result = sync_manga_status(
            "reading",
            save_raw=False,
            client=FakeMangaListClient(
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

        manga = MangaEntry.objects.get(
            mal_id=200
        )

        self.assertEqual(
            manga.title_japanese,
            "テストマンガ",
        )
        self.assertEqual(
            manga.title_english,
            "Test Manga",
        )
        self.assertEqual(
            manga.num_chapters_read,
            1,
        )

        second_result = sync_manga_status(
            "reading",
            save_raw=False,
            client=FakeMangaListClient(
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

        changed_item = build_manga_item(
            chapters_read=2,
        )

        third_result = sync_manga_status(
            "reading",
            save_raw=False,
            client=FakeMangaListClient(
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

        manga.refresh_from_db()

        self.assertEqual(
            manga.num_chapters_read,
            2,
        )

    def test_picture_extension_variants_are_unchanged(
        self,
    ):
        initial_item = build_manga_item()

        sync_manga_status(
            "reading",
            save_raw=False,
            client=FakeMangaListClient(
                [initial_item]
            ),
        )

        picture_variant = build_manga_item()

        picture_variant[
            "node"
        ][
            "main_picture"
        ][
            "large"
        ] = (
            "https://example.com/"
            "manga-large.webp"
        )

        result = sync_manga_status(
            "reading",
            save_raw=False,
            client=FakeMangaListClient(
                [picture_variant]
            ),
        )

        self.assertEqual(
            result["created"],
            0,
        )
        self.assertEqual(
            result["updated"],
            0,
        )
        self.assertEqual(
            result["unchanged"],
            1,
        )


class MangaLibrarySyncViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects
            .create_user(
                username="manga-owner",
            )
        )

    @patch(
        (
            "mal_data.web.manga_sync."
            "sync_all_manga_statuses"
        )
    )
    def test_authenticated_post_syncs_and_redirects(
        self,
        mock_sync,
    ):
        mock_sync.return_value = [
            {
                "status": "reading",
                "total": 2,
                "created": 1,
                "updated": 1,
                "unchanged": 0,
            },
            {
                "status": "completed",
                "total": 3,
                "created": 0,
                "updated": 0,
                "unchanged": 3,
            },
        ]

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "manga_insights:"
                "sync_manga_library"
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "manga_insights:dashboard"
            ),
            fetch_redirect_response=False,
        )

        mock_sync.assert_called_once_with()


class MangaArchiveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reading = MangaEntry.objects.create(
            mal_id=4001,
            title="Reading Manga",
            title_japanese="読書漫画",
            media_type="manga",
            publication_status=(
                "currently_publishing"
            ),
            list_status="reading",
            num_chapters_read=12,
            num_volumes_read=2,
        )

        cls.rereading = (
            MangaEntry.objects.create(
                mal_id=4002,
                title="Rereading Manga",
                media_type="manga",
                publication_status="finished",
                list_status="completed",
                is_rereading=True,
                num_chapters_read=50,
                num_volumes_read=8,
            )
        )

        cls.light_novel = (
            MangaEntry.objects.create(
                mal_id=4003,
                title="Light Novel",
                media_type="light_novel",
                publication_status="finished",
                list_status="plan_to_read",
            )
        )

    def test_manga_archive_routes_are_public(
        self,
    ):
        for status in (
            "all",
            "reading",
            "completed",
            "plan_to_read",
            "on_hold",
            "dropped",
        ):
            with self.subTest(status=status):
                response = self.client.get(
                    reverse(
                        "manga_insights:"
                        "manga_status_list",
                        kwargs={
                            "status": status,
                        },
                    )
                )

                self.assertEqual(
                    response.status_code,
                    200,
                )

    def test_reading_includes_rereading(
        self,
    ):
        response = self.client.get(
            reverse(
                "manga_insights:"
                "manga_status_list",
                kwargs={
                    "status": "reading",
                },
            )
        )

        manga_ids = {
            manga.mal_id
            for manga
            in response.context[
                "manga_entries"
            ]
        }

        self.assertEqual(
            manga_ids,
            {
                self.reading.mal_id,
                self.rereading.mal_id,
            },
        )

    def test_archive_filters_publication_and_type(
        self,
    ):
        response = self.client.get(
            reverse(
                "manga_insights:"
                "manga_status_list",
                kwargs={
                    "status": "all",
                },
            ),
            {
                "publication": "finished",
                "media_type": "light_novel",
            },
        )

        self.assertEqual(
            response.context["total_entries"],
            1,
        )

        self.assertEqual(
            response.context[
                "manga_entries"
            ][0].mal_id,
            self.light_novel.mal_id,
        )

    def test_invalid_manga_status_returns_404(
        self,
    ):
        response = self.client.get(
            reverse(
                "manga_insights:"
                "manga_status_list",
                kwargs={
                    "status": "invalid",
                },
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )


class MangaReadingProgressTests(TestCase):
    def test_targets_include_reading_and_rereading(
        self,
    ):
        reading = MangaEntry.objects.create(
            mal_id=5001,
            title="Reading",
            list_status="reading",
        )

        rereading = MangaEntry.objects.create(
            mal_id=5002,
            title="Rereading",
            list_status="completed",
            is_rereading=True,
        )

        MangaEntry.objects.create(
            mal_id=5003,
            title="Completed",
            list_status="completed",
        )

        MangaEntry.objects.create(
            mal_id=5004,
            title="Plan",
            list_status="plan_to_read",
        )

        target_ids = set(
            get_active_reading_entries()
            .values_list(
                "mal_id",
                flat=True,
            )
        )

        self.assertEqual(
            target_ids,
            {
                reading.mal_id,
                rereading.mal_id,
            },
        )

    @patch(
        (
            "mal_data.services."
            "manga_reading_sync."
            "MyAnimeListClient"
        )
    )
    def test_sync_updates_progress_and_logs(
        self,
        mock_client_class,
    ):
        manga = MangaEntry.objects.create(
            mal_id=5100,
            title="Active Manga",
            list_status="reading",
            score=8,
            num_chapters_read=10,
            num_volumes_read=2,
        )

        tracked_entry = (
            ManualTrackedManga.objects.create(
                mal_id=manga.mal_id,
                title_snapshot=manga.title,
                status="reading",
                chapters_read=10,
                volumes_read=2,
                score=8,
                active=True,
            )
        )

        mal_client = Mock()
        mal_client.fetch_manga_my_list_status.return_value = {
            "status": "completed",
            "score": 9,
            "num_chapters_read": 12,
            "num_volumes_read": 3,
            "is_rereading": False,
            "updated_at": (
                "2026-07-27T16:00:00+00:00"
            ),
        }

        mal_client.fetch_all_manga_by_status.return_value = [
            {
                "page": 1,
                "entries": [],
                "total_accumulated": 0,
            }
        ]

        mock_client_class.return_value = (
            mal_client
        )

        results = sync_reading_progress()

        manga.refresh_from_db()

        tracked_entry.refresh_from_db()

        self.assertEqual(
            tracked_entry.status,
            "completed",
        )
        self.assertEqual(
            tracked_entry.chapters_read,
            12,
        )
        self.assertEqual(
            tracked_entry.volumes_read,
            3,
        )
        self.assertEqual(
            tracked_entry.score,
            9,
        )

        self.assertEqual(
            manga.list_status,
            "completed",
        )
        self.assertEqual(
            manga.num_chapters_read,
            12,
        )
        self.assertEqual(
            manga.num_volumes_read,
            3,
        )
        self.assertEqual(manga.score, 9)

        self.assertTrue(
            results["personal"][0]["changed"]
        )
        self.assertEqual(
            results["active_after"],
            0,
        )

        self.assertEqual(
            results["list_checked"],
            0,
        )
        self.assertEqual(
            results["manual_checked"],
            1,
        )
        self.assertEqual(
            results["reconciled_checked"],
            0,
        )

        event_types = set(
            MangaSyncEvent.objects
            .filter(manga=manga)
            .values_list(
                "event_type",
                flat=True,
            )
        )

        self.assertEqual(
            event_types,
            {
                "status_changed",
                "chapter_changed",
                "volume_changed",
                "score_changed",
            },
        )


    @patch(
        (
            "mal_data.services."
            "manga_reading_sync."
            "MyAnimeListClient"
        )
    )
    def test_normal_reading_uses_reading_list(
        self,
        mock_client_class,
    ):
        manga = MangaEntry.objects.create(
            mal_id=5300,
            title="Normal Reading",
            list_status="reading",
            num_chapters_read=10,
            num_volumes_read=1,
        )

        reading_item = build_manga_item(
            mal_id=manga.mal_id,
            title=manga.title,
            status="reading",
            chapters_read=11,
            volumes_read=1,
            score=8,
        )

        mal_client = Mock()

        mal_client.fetch_all_manga_by_status.return_value = [
            {
                "page": 1,
                "entries": [reading_item],
                "total_accumulated": 1,
            }
        ]

        mock_client_class.return_value = (
            mal_client
        )

        results = sync_reading_progress()

        manga.refresh_from_db()

        self.assertEqual(
            manga.num_chapters_read,
            11,
        )
        self.assertEqual(
            results["list_checked"],
            1,
        )
        self.assertEqual(
            results["manual_checked"],
            0,
        )
        self.assertEqual(
            results["reconciled_checked"],
            0,
        )

        mal_client.fetch_manga_my_list_status\
            .assert_not_called()


class MangaReadingProgressViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects
            .create_user(
                username="reading-owner",
            )
        )

    @patch(
        (
            "mal_data.web.manga_sync."
            "get_actionable_chapter_signals"
        )
    )
    @patch(
        (
            "mal_data.web.manga_sync."
            "sync_all_external_chapter_signals"
        )
    )
    @patch(
        (
            "mal_data.web.manga_sync."
            "sync_canonical_chapter_signals"
        )
    )
    @patch(
        (
            "mal_data.web.manga_sync."
            "sync_reading_progress"
        )
    )
    def test_authenticated_post_syncs_and_redirects(
        self,
        mock_reading_sync,
        mock_signal_sync,
        mock_external_sync,
        mock_get_actionable,
    ):
        mock_reading_sync.return_value = {
            "personal": [
                {
                    "changed": True,
                    "ok": True,
                }
            ],
            "list_checked": 1,
            "manual_checked": 0,
            "reconciled_checked": 0,
            "active_after": 1,
        }

        mock_signal_sync.return_value = {
            "targets": 1,
            "created": 1,
            "updated": 0,
            "unchanged": 0,
            "actionable": 1,
        }

        mock_external_sync.return_value = {
            "targets": 1,
            "created": 0,
            "updated": 1,
            "unchanged": 0,
            "empty": 0,
            "errors": 0,
            "fallbacks": 0,
            "results": [
                {
                    "mal_id": 162479,
                    "title": "Kagurabachi",
                    "provider": "weeb_central",
                    "status": "updated",
                    "ok": True,
                    "error": None,
                    "used_fallback": False,
                }
            ],
        }

        mock_get_actionable.return_value = [
            Mock(),
        ]

        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "manga_insights:"
                "sync_reading_progress"
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "manga_insights:dashboard"
            ),
            fetch_redirect_response=False,
        )

        mock_reading_sync.assert_called_once_with()
        mock_signal_sync.assert_called_once_with()
        mock_external_sync.assert_called_once_with()
        mock_get_actionable.assert_called_once_with()


class MangaCommandLogDashboardTests(TestCase):
    def test_dashboard_displays_manga_command_log(
        self,
    ):
        manga = MangaEntry.objects.create(
            mal_id=5200,
            title="Logged Manga",
            list_status="reading",
        )

        MangaSyncEvent.objects.create(
            manga=manga,
            mal_id=manga.mal_id,
            title_snapshot=manga.title,
            event_type="chapter_changed",
            old_value="CH. 4",
            new_value="CH. 5",
        )

        response = self.client.get(
            reverse(
                "manga_insights:dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "CH_UPDATE:",
        )
        self.assertContains(
            response,
            "CH. 4",
        )
        self.assertContains(
            response,
            "CH. 5",
        )


class ManualMangaRescueSyncViewTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects
            .create_user(
                username=(
                    "manual-manga-owner"
                ),
            )
        )

    @patch(
        (
            "mal_data.web.manga_sync."
            "sync_all_manual_tracked_manga"
        )
    )
    def test_authenticated_post_syncs_rescues(
        self,
        mock_sync,
    ):
        mock_sync.return_value = [
            {
                "mal_id": 125255,
                "title": (
                    "Yankee JK "
                    "Kuzuhana-chan"
                ),
                "status": "reading",
                "created": False,
                "ok": True,
                "error": None,
            }
        ]

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "manga_insights:"
                "sync_manual_manga_rescues"
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "manga_insights:dashboard"
            ),
            fetch_redirect_response=False,
        )

        mock_sync.assert_called_once_with()


class MangaCanonicalChapterSignalTests(
    TestCase
):
    def test_finished_reading_exposes_pending_total(
        self,
    ):
        manga = MangaEntry.objects.create(
            mal_id=6101,
            title="Finished Reading",
            list_status="reading",
            publication_status="finished",
            num_chapters_read=42,
            num_chapters=71,
        )

        results = (
            sync_canonical_chapter_signals()
        )

        signal = (
            MangaChapterSignal.objects.get(
                manga=manga
            )
        )

        self.assertEqual(
            signal.canonical_target_chapter,
            71,
        )
        self.assertEqual(
            signal.chapters_to_complete,
            29,
        )
        self.assertEqual(
            signal.pending_chapters,
            29,
        )
        self.assertTrue(signal.has_signal)
        self.assertEqual(
            signal.signal_kind,
            "canonical",
        )

        self.assertEqual(
            results["targets"],
            1,
        )
        self.assertEqual(
            results["actionable"],
            1,
        )

    def test_sync_targets_reading_and_rereading_only(
        self,
    ):
        reading = MangaEntry.objects.create(
            mal_id=6102,
            title="Publishing Reading",
            list_status="reading",
            publication_status=(
                "currently_publishing"
            ),
            num_chapters_read=10,
            num_chapters=0,
        )

        rereading = MangaEntry.objects.create(
            mal_id=6103,
            title="Finished Rereading",
            list_status="completed",
            is_rereading=True,
            publication_status="finished",
            num_chapters_read=5,
            num_chapters=20,
        )

        MangaEntry.objects.create(
            mal_id=6104,
            title="Inactive Completed",
            list_status="completed",
            publication_status="finished",
            num_chapters_read=5,
            num_chapters=20,
        )

        results = (
            sync_canonical_chapter_signals()
        )

        signal_ids = set(
            MangaChapterSignal.objects
            .values_list(
                "mal_id",
                flat=True,
            )
        )

        self.assertEqual(
            signal_ids,
            {
                reading.mal_id,
                rereading.mal_id,
            },
        )
        self.assertEqual(
            results["targets"],
            2,
        )
        self.assertEqual(
            results["actionable"],
            1,
        )

    def test_live_publishing_signal_precedes_finished(
        self,
    ):
        publishing = (
            MangaEntry.objects.create(
                mal_id=6105,
                title="Weekly Publishing",
                list_status="reading",
                publication_status=(
                    "currently_publishing"
                ),
                num_chapters_read=10,
            )
        )

        finished = MangaEntry.objects.create(
            mal_id=6106,
            title="Finished Backlog",
            list_status="reading",
            publication_status="finished",
            num_chapters_read=42,
            num_chapters=71,
        )

        MangaChapterSignal.objects.create(
            manga=publishing,
            mal_id=publishing.mal_id,
            latest_available_chapter=12,
            availability_source_type=(
                "external"
            ),
            availability_source_name=(
                "Test Source"
            ),
        )

        MangaChapterSignal.objects.create(
            manga=finished,
            mal_id=finished.mal_id,
            canonical_total_chapters=71,
        )

        signals = (
            get_actionable_chapter_signals()
        )

        self.assertEqual(
            [
                signal.mal_id
                for signal in signals
            ],
            [
                publishing.mal_id,
                finished.mal_id,
            ],
        )


class MangaDashboardMirrorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects
            .create_user(
                username="manga-dashboard-owner",
            )
        )

        cls.reading = MangaEntry.objects.create(
            mal_id=6001,
            title="Reading Spotlight",
            title_japanese="読書スポットライト",
            list_status="reading",
            score=9,
            num_chapters_read=10,
            num_chapters=20,
        )

        MangaChapterSignal.objects.create(
            manga=cls.reading,
            mal_id=cls.reading.mal_id,
            canonical_total_chapters=20,
        )

        MangaEntry.objects.create(
            mal_id=6002,
            title="Completed Manga",
            list_status="completed",
        )

        MangaEntry.objects.create(
            mal_id=6003,
            title="Plan Manga",
            list_status="plan_to_read",
        )

    def test_dashboard_uses_mirrored_command_center(
        self,
    ):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("manga_insights:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context[
                "backlog_clear_ratio"
            ],
            50,
        )

        self.assertEqual(
            response.context[
                "spotlight_manga"
            ].mal_id,
            self.reading.mal_id,
        )

        for content in (
            "User Profile",
            "Backlog Clear Ratio",
            "JP Title Signal",
            "Chapter Signals",
            "TO COMPLETE",
            "Manga Library Nodes",
            "Manga Command Logs",
            "Sync Manga Library",
            "Sync Manual Rescues",
            "Connect / Renew MAL",
        ):
            with self.subTest(content=content):
                self.assertContains(
                    response,
                    content,
                )


class WeebCentralClientTests(
    SimpleTestCase
):
    def test_parse_search_candidates(self):
        html = """
        <article>
            <section>
                <a
                    href="/series/SOURCE123/Kagurabachi"
                >
                    <picture>
                        <source
                            srcset="/covers/kagurabachi.webp"
                        >
                    </picture>

                    <div>
                        Metadata
                    </div>

                    <div>
                        Kagurabachi
                    </div>
                </a>
            </section>
        </article>
        """

        candidates = (
            WeebCentralClient
            .parse_search_html(html)
        )

        self.assertEqual(
            len(candidates),
            1,
        )
        self.assertEqual(
            candidates[0].source_id,
            "SOURCE123",
        )
        self.assertEqual(
            candidates[0].title,
            "Kagurabachi",
        )
        self.assertEqual(
            candidates[0].url,
            (
                "https://weebcentral.com/"
                "series/SOURCE123/"
                "Kagurabachi"
            ),
        )

    def test_parse_chapter_list(self):
        html = """
        <div x-data="chapter-list">
            <a href="/chapters/CHAPTER126">
                <span class="flex">
                    <span>Chapter 126</span>
                </span>

                <time
                    datetime="2026-07-26T15:05:59Z"
                ></time>
            </a>

            <a href="/chapters/CHAPTER1255">
                <span class="flex">
                    <span>Chapter 125.5</span>
                </span>
            </a>
        </div>
        """

        chapters = (
            WeebCentralClient
            .parse_chapter_list_html(html)
        )

        self.assertEqual(
            len(chapters),
            2,
        )
        self.assertEqual(
            chapters[0].number,
            Decimal("126"),
        )
        self.assertEqual(
            chapters[1].number,
            Decimal("125.5"),
        )

    def test_exact_source_title_scores_first(
        self,
    ):
        self.assertEqual(
            source_title_score(
                "Kagurabachi",
                "Kagurabachi",
            ),
            100.0,
        )

        self.assertGreater(
            source_title_score(
                "Kagurabachi",
                "Kagurabachi Official",
            ),
            source_title_score(
                "Kagurabachi",
                "Blue Lock",
            ),
        )


class FakeMangaPlusAPI:
    def __init__(self):
        self.secret = "test-secret"

    def getTitleDetail(self, title_id):
        return {
            "titleDetailView": {
                "title": {
                    "titleId": str(
                        title_id
                    ),
                    "name": "Kagurabachi",
                    "portraitImageUrl": (
                        "https://example.test/"
                        "kagurabachi.jpg"
                    ),
                },
                "chapterListV2": [
                    {
                        "chapterId": (
                            "1012600"
                        ),
                        "name": "#126",
                        "startTimeStamp": (
                            "1785078000"
                        ),
                    },
                    {
                        "chapterId": (
                            "1012500"
                        ),
                        "name": "#125",
                        "startTimeStamp": (
                            "1784473200"
                        ),
                    },
                ],
            }
        }

    def getSearchTitles(self):
        return {
            "searchView": {
                "allTitlesGroup": [
                    {
                        "titles": [
                            {
                                "titleId": (
                                    "100274"
                                ),
                                "name": (
                                    "Kagurabachi"
                                ),
                                "portraitImageUrl": (
                                    "https://"
                                    "example.test/"
                                    "cover.jpg"
                                ),
                            }
                        ]
                    }
                ]
            }
        }


class MangaPlusClientTests(
    SimpleTestCase
):
    def setUp(self):
        self.client = MangaPlusClient(
            api_client=FakeMangaPlusAPI()
        )

    def test_direct_title_id_search(self):
        candidates = self.client.search(
            "100274"
        )

        self.assertEqual(
            len(candidates),
            1,
        )
        self.assertEqual(
            candidates[0].source_id,
            "100274",
        )
        self.assertEqual(
            candidates[0].title,
            "Kagurabachi",
        )
        self.assertEqual(
            candidates[0].url,
            (
                "https://"
                "mangaplus.shueisha.co.jp/"
                "titles/100274"
            ),
        )

    def test_text_catalog_search(self):
        candidates = self.client.search(
            "Kagurabachi"
        )

        self.assertEqual(
            len(candidates),
            1,
        )
        self.assertEqual(
            candidates[0].source_id,
            "100274",
        )

    def test_fetch_latest_chapter(self):
        latest = (
            self.client
            .fetch_latest_chapter(
                (
                    "https://"
                    "mangaplus.shueisha.co.jp/"
                    "titles/100274"
                )
            )
        )

        self.assertIsNotNone(latest)
        self.assertEqual(
            latest.number,
            Decimal("126"),
        )
        self.assertEqual(
            latest.label,
            "#126",
        )


class InspectMangaSourceCommandTests(
    TestCase
):
    def setUp(self):
        self.manga = MangaEntry.objects.create(
            mal_id=162479,
            title="Kagurabachi",
            title_japanese="カグラバチ",
            list_status="reading",
            publication_status=(
                "currently_publishing"
            ),
        )

    def create_source_link(
        self,
        *,
        provider="weeb_central",
        priority=1,
        active=True,
    ):
        return MangaSourceLink.objects.create(
            manga=self.manga,
            provider=provider,
            source_id=(
                f"{provider}-source-id"
            ),
            source_title="Kagurabachi",
            source_url=(
                "https://example.test/"
                f"{provider}/kagurabachi"
            ),
            match_score=Decimal("100"),
            search_query="Kagurabachi",
            priority=priority,
            active=active,
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_resolver."
            "build_provider_client"
        )
    )
    def test_uses_highest_priority_active_source(
        self,
        mock_build_client,
    ):
        self.create_source_link(
            provider="weeb_central",
            priority=2,
        )
        self.create_source_link(
            provider="manga_plus",
            priority=1,
        )

        client = Mock()
        client.fetch_latest_chapter.return_value = (
            SimpleNamespace(
                number=Decimal("68"),
                label="Chapter 68",
                url=(
                    "https://example.test/"
                    "chapters/68"
                ),
                published_at=None,
            )
        )

        mock_build_client.return_value = (
            client
        )

        output = StringIO()

        call_command(
            "inspect_manga_source",
            self.manga.mal_id,
            stdout=output,
        )

        mock_build_client.assert_called_once_with(
            "manga_plus"
        )

        client.fetch_latest_chapter\
            .assert_called_once_with(
                (
                    "https://example.test/"
                    "manga_plus/kagurabachi"
                )
            )

        command_output = output.getvalue()

        self.assertIn(
            "Provider: manga_plus",
            command_output,
        )
        self.assertIn(
            "Priority: 1",
            command_output,
        )
        self.assertIn(
            "Latest chapter: 68",
            command_output,
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_resolver."
            "build_provider_client"
        )
    )
    def test_explicit_provider_overrides_priority(
        self,
        mock_build_client,
    ):
        self.create_source_link(
            provider="weeb_central",
            priority=2,
        )

        client = Mock()
        client.fetch_latest_chapter.return_value = (
            SimpleNamespace(
                number=Decimal("67"),
                label="Chapter 67",
                url=(
                    "https://example.test/"
                    "chapters/67"
                ),
                published_at=None,
            )
        )

        mock_build_client.return_value = (
            client
        )

        output = StringIO()

        call_command(
            "inspect_manga_source",
            self.manga.mal_id,
            provider="weeb_central",
            stdout=output,
        )

        mock_build_client.assert_called_once_with(
            "weeb_central"
        )

        self.assertIn(
            "Provider: weeb_central",
            output.getvalue(),
        )
        self.assertIn(
            "Latest chapter: 67",
            output.getvalue(),
        )

    def test_inactive_source_is_not_used(
        self,
    ):
        self.create_source_link(
            active=False
        )

        with self.assertRaisesMessage(
            CommandError,
            (
                "No active saved manga "
                "source exists"
            ),
        ):
            call_command(
                "inspect_manga_source",
                self.manga.mal_id,
            )


class MangaExternalChapterSignalTests(
    TestCase
):
    def setUp(self):
        self.manga = MangaEntry.objects.create(
            mal_id=162479,
            title="Kagurabachi",
            list_status="reading",
            publication_status=(
                "currently_publishing"
            ),
            num_chapters_read=65,
        )

        self.source_link = (
            MangaSourceLink.objects.create(
                manga=self.manga,
                provider="weeb_central",
                source_id="SOURCE123",
                source_title="Kagurabachi",
                source_url=(
                    "https://weebcentral.com/"
                    "series/SOURCE123/"
                    "Kagurabachi"
                ),
                priority=1,
                active=True,
            )
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_signal_sync."
            "fetch_latest_saved_chapter"
        )
    )
    def test_creates_external_chapter_signal(
        self,
        mock_fetch_latest,
    ):
        mock_fetch_latest.return_value = (
            self.source_link,
            SimpleNamespace(
                source_id="CHAPTER68",
                label="Chapter 68",
                number=Decimal("68"),
                url=(
                    "https://weebcentral.com/"
                    "chapters/CHAPTER68"
                ),
                published_at=None,
            ),
            [
                {
                    "provider": "weeb_central",
                    "priority": 1,
                    "status": "success",
                    "ok": True,
                    "error": None,
                }
            ],
        )

        result = (
            sync_external_chapter_signal(
                self.manga
            )
        )

        signal = (
            MangaChapterSignal.objects.get(
                manga=self.manga
            )
        )

        self.assertTrue(
            result["created"]
        )
        self.assertTrue(
            result["changed"]
        )
        self.assertEqual(
            signal.latest_available_chapter,
            Decimal("68"),
        )
        self.assertEqual(
            signal.availability_source_type,
            "external",
        )
        self.assertEqual(
            signal.availability_source_name,
            "Weeb Central",
        )
        self.assertEqual(
            signal.pending_chapters,
            Decimal("3"),
        )
        self.assertIsNotNone(
            signal.external_checked_at
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_signal_sync."
            "fetch_latest_saved_chapter"
        )
    )
    def test_preserves_canonical_total(
        self,
        mock_fetch_latest,
    ):
        MangaChapterSignal.objects.create(
            manga=self.manga,
            mal_id=self.manga.mal_id,
            canonical_total_chapters=100,
        )

        mock_fetch_latest.return_value = (
            self.source_link,
            SimpleNamespace(
                source_id="CHAPTER68",
                label="Chapter 68",
                number=Decimal("68"),
                url=(
                    "https://weebcentral.com/"
                    "chapters/CHAPTER68"
                ),
                published_at=None,
            ),
            [
                {
                    "provider": "weeb_central",
                    "priority": 1,
                    "status": "success",
                    "ok": True,
                    "error": None,
                }
            ],
        )

        sync_external_chapter_signal(
            self.manga
        )

        signal = (
            MangaChapterSignal.objects.get(
                manga=self.manga
            )
        )

        self.assertEqual(
            signal.canonical_total_chapters,
            100,
        )
        self.assertEqual(
            signal.latest_available_chapter,
            Decimal("68"),
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_signal_sync."
            "fetch_latest_saved_chapter"
        )
    )
    def test_no_chapters_does_not_create_signal(
        self,
        mock_fetch_latest,
    ):
        mock_fetch_latest.return_value = (
            self.source_link,
            None,
            [
                {
                    "provider": "weeb_central",
                    "priority": 1,
                    "status": "empty",
                    "ok": True,
                    "error": None,
                }
            ],
        )

        result = (
            sync_external_chapter_signal(
                self.manga
            )
        )

        self.assertFalse(
            result["created"]
        )
        self.assertFalse(
            result["changed"]
        )
        self.assertFalse(
            MangaChapterSignal.objects
            .filter(
                manga=self.manga
            )
            .exists()
        )


class MangaExternalChapterSignalBatchTests(
    TestCase
):
    def create_target(
        self,
        *,
        mal_id,
        title,
        list_status="reading",
        active_source=True,
    ):
        manga = MangaEntry.objects.create(
            mal_id=mal_id,
            title=title,
            list_status=list_status,
            publication_status=(
                "currently_publishing"
            ),
        )

        source_link = (
            MangaSourceLink.objects.create(
                manga=manga,
                provider="weeb_central",
                source_id=(
                    f"SOURCE-{mal_id}"
                ),
                source_title=title,
                source_url=(
                    "https://weebcentral.com/"
                    f"series/SOURCE-{mal_id}/"
                    f"{title}"
                ),
                priority=1,
                active=active_source,
            )
        )

        return manga, source_link

    @patch(
        (
            "mal_data.services."
            "manga_source_signal_sync."
            "sync_external_chapter_signal"
        )
    )
    def test_continues_after_individual_error(
        self,
        mock_sync_external,
    ):
        first_manga, first_source = (
            self.create_target(
                mal_id=7001,
                title="Alpha Manga",
            )
        )

        second_manga, second_source = (
            self.create_target(
                mal_id=7002,
                title="Beta Manga",
            )
        )

        def fake_sync(manga):
            if manga == first_manga:
                raise RuntimeError(
                    "Provider unavailable"
                )

            return {
                "source_link": second_source,
                "latest_chapter": (
                    SimpleNamespace(
                        number=Decimal("12")
                    )
                ),
                "signal": None,
                "created": False,
                "changed": False,
            }

        mock_sync_external.side_effect = (
            fake_sync
        )

        results = (
            sync_all_external_chapter_signals()
        )

        self.assertEqual(
            results["targets"],
            2,
        )
        self.assertEqual(
            results["errors"],
            1,
        )
        self.assertEqual(
            results["unchanged"],
            1,
        )
        self.assertEqual(
            mock_sync_external.call_count,
            2,
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_signal_sync."
            "sync_external_chapter_signal"
        )
    )
    def test_ignores_inactive_sources(
        self,
        mock_sync_external,
    ):
        self.create_target(
            mal_id=7003,
            title="Inactive Source",
            active_source=False,
        )

        results = (
            sync_all_external_chapter_signals()
        )

        self.assertEqual(
            results["targets"],
            0,
        )

        mock_sync_external.assert_not_called()


class MangaSourceFallbackTests(
    TestCase
):
    def setUp(self):
        self.manga = MangaEntry.objects.create(
            mal_id=162479,
            title="Kagurabachi",
            list_status="reading",
        )

        MangaSourceLink.objects.create(
            manga=self.manga,
            provider="manga_plus",
            source_id="100274",
            source_title="Kagurabachi",
            source_url=(
                "https://"
                "mangaplus.shueisha.co.jp/"
                "titles/100274"
            ),
            priority=1,
            active=True,
        )

        MangaSourceLink.objects.create(
            manga=self.manga,
            provider="weeb_central",
            source_id="SOURCE123",
            source_title="Kagurabachi",
            source_url=(
                "https://weebcentral.com/"
                "series/SOURCE123/"
                "Kagurabachi"
            ),
            priority=2,
            active=True,
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_resolver."
            "build_provider_client"
        )
    )
    def test_uses_fallback_when_primary_fails(
        self,
        mock_build_client,
    ):
        manga_plus_client = Mock()
        manga_plus_client\
            .fetch_latest_chapter\
            .side_effect = RuntimeError(
                "MANGA Plus unavailable"
            )

        weeb_central_client = Mock()
        weeb_central_client\
            .fetch_latest_chapter\
            .return_value = (
                SimpleNamespace(
                    number=Decimal("126")
                )
            )

        clients = {
            "manga_plus": (
                manga_plus_client
            ),
            "weeb_central": (
                weeb_central_client
            ),
        }

        mock_build_client.side_effect = (
            lambda provider: clients[
                provider
            ]
        )

        (
            source_link,
            latest_chapter,
            attempts,
        ) = fetch_latest_saved_chapter(
            self.manga
        )

        self.assertEqual(
            source_link.provider,
            "weeb_central",
        )
        self.assertEqual(
            latest_chapter.number,
            Decimal("126"),
        )
        self.assertEqual(
            len(attempts),
            2,
        )
        self.assertEqual(
            attempts[0]["status"],
            "error",
        )
        self.assertEqual(
            attempts[1]["status"],
            "success",
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_resolver."
            "build_provider_client"
        )
    )
    def test_explicit_provider_does_not_fallback(
        self,
        mock_build_client,
    ):
        client = Mock()
        client.fetch_latest_chapter.side_effect = (
            RuntimeError(
                "MANGA Plus unavailable"
            )
        )

        mock_build_client.return_value = (
            client
        )

        with self.assertRaises(
            MangaSourceFetchError
        ):
            fetch_latest_saved_chapter(
                self.manga,
                provider="manga_plus",
            )

        mock_build_client\
            .assert_called_once_with(
                "manga_plus"
            )


class MangaSourceManagementViewTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects
            .create_user(
                username=(
                    "manga-source-owner"
                ),
            )
        )

        cls.manga = MangaEntry.objects.create(
            mal_id=162479,
            title="Kagurabachi",
            title_japanese="カグラバチ",
            list_status="reading",
            publication_status=(
                "currently_publishing"
            ),
            num_chapters_read=102,
        )

        MangaSourceLink.objects.create(
            manga=cls.manga,
            provider="weeb_central",
            source_id="SOURCE123",
            source_title="Kagurabachi",
            source_url=(
                "https://weebcentral.com/"
                "series/SOURCE123/"
                "Kagurabachi"
            ),
            priority=2,
            active=True,
        )

        MangaSourceLink.objects.create(
            manga=cls.manga,
            provider="manga_plus",
            source_id="100274",
            source_title="Kagurabachi",
            source_url=(
                "https://"
                "mangaplus.shueisha.co.jp/"
                "titles/100274"
            ),
            priority=1,
            active=True,
            is_official=True,
        )

    def get_url(self):
        return reverse(
            "manga_insights:"
            "manga_source_management",
            kwargs={
                "mal_id": self.manga.mal_id,
            },
        )

    def test_anonymous_request_redirects_to_login(
        self,
    ):
        response = self.client.get(
            self.get_url()
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertTrue(
            response.url.startswith(
                f"{reverse('login')}?next="
            )
        )

    def test_owner_sees_sources_in_priority_order(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            self.get_url()
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context["manga"],
            self.manga,
        )

        providers = [
            row["link"].provider
            for row in response.context[
                "source_rows"
            ]
        ]

        self.assertEqual(
            providers,
            [
                "manga_plus",
                "weeb_central",
            ],
        )

        self.assertContains(
            response,
            "MANGA Plus",
        )
        self.assertContains(
            response,
            "Weeb Central",
        )
        self.assertContains(
            response,
            "Primary",
        )
        self.assertContains(
            response,
            "Fallback",
        )

    def test_unknown_manga_returns_404(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            reverse(
                "manga_insights:"
                "manga_source_management",
                kwargs={
                    "mal_id": 999999,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    @patch(
        (
            "mal_data.web.manga_sources."
            "search_manga_sources"
        )
    )
    def test_owner_can_search_source_candidates(
        self,
        mock_search,
    ):
        mock_search.return_value = (
            SimpleNamespace(
                provider="manga_plus",
                query="100274",
                candidates=(
                    SimpleNamespace(
                        position=1,
                        score=Decimal("100.00"),
                        source_id="100274",
                        title="Kagurabachi",
                        url=(
                            "https://"
                            "mangaplus.shueisha.co.jp/"
                            "titles/100274"
                        ),
                        thumbnail_url=None,
                    ),
                ),
            )
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            self.get_url(),
            {
                "search": "1",
                "provider": "manga_plus",
                "query": "100274",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        mock_search.assert_called_once_with(
            self.manga,
            provider="manga_plus",
            query="100274",
            limit=10,
        )

        self.assertContains(
            response,
            "Search Sources",
        )
        self.assertContains(
            response,
            "Kagurabachi",
        )
        self.assertContains(
            response,
            "Primary",
        )
        self.assertContains(
            response,
            "Fallback",
        )


    @patch(
        (
            "mal_data.web.manga_sources."
            "save_manga_source_candidate_with_role"
        )
    )
    @patch(
        (
            "mal_data.web.manga_sources."
            "search_manga_sources"
        )
    )
    def test_owner_can_save_primary_source(
        self,
        mock_search,
        mock_save,
    ):
        candidate = SimpleNamespace(
            position=1,
            score=Decimal("100.00"),
            source_id="100274",
            title="Kagurabachi",
            url=(
                "https://"
                "mangaplus.shueisha.co.jp/"
                "titles/100274"
            ),
            thumbnail_url=None,
        )

        mock_search.return_value = (
            SimpleNamespace(
                provider="manga_plus",
                query="100274",
                candidates=(candidate,),
            )
        )

        source_link = (
            MangaSourceLink.objects.get(
                manga=self.manga,
                provider="manga_plus",
            )
        )

        mock_save.return_value = (
            source_link,
            False,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                (
                    "manga_insights:"
                    "save_manga_source"
                ),
                kwargs={
                    "mal_id": self.manga.mal_id,
                },
            ),
            {
                "provider": "manga_plus",
                "query": "100274",
                "source_id": "100274",
                "role": "primary",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        mock_search.assert_called_once_with(
            self.manga,
            provider="manga_plus",
            query="100274",
            limit=32,
        )

        mock_save.assert_called_once_with(
            self.manga,
            provider="manga_plus",
            candidate=candidate,
            search_query="100274",
            role="primary",
        )

    def test_owner_can_make_fallback_primary(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        weeb_source = (
            MangaSourceLink.objects.get(
                manga=self.manga,
                provider="weeb_central",
            )
        )

        response = self.client.post(
            reverse(
                (
                    "manga_insights:"
                    "make_manga_source_primary"
                ),
                kwargs={
                    "mal_id": self.manga.mal_id,
                    "link_id": weeb_source.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        weeb_source.refresh_from_db()

        self.assertEqual(
            weeb_source.priority,
            1,
        )


    def test_owner_can_toggle_source(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        source_link = (
            MangaSourceLink.objects.get(
                manga=self.manga,
                provider="manga_plus",
            )
        )

        self.client.post(
            reverse(
                (
                    "manga_insights:"
                    "toggle_manga_source_active"
                ),
                kwargs={
                    "mal_id": self.manga.mal_id,
                    "link_id": source_link.pk,
                },
            )
        )

        source_link.refresh_from_db()

        self.assertFalse(
            source_link.active
        )


    def test_owner_can_unlink_source(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        source_link = (
            MangaSourceLink.objects.get(
                manga=self.manga,
                provider="manga_plus",
            )
        )

        response = self.client.post(
            reverse(
                (
                    "manga_insights:"
                    "unlink_manga_source"
                ),
                kwargs={
                    "mal_id": self.manga.mal_id,
                    "link_id": source_link.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertFalse(
            MangaSourceLink.objects
            .filter(
                pk=source_link.pk
            )
            .exists()
        )


    @patch(
        (
            "mal_data.web.manga_sources."
            "sync_external_chapter_signal"
        )
    )
    def test_owner_can_sync_source_now(
        self,
        mock_sync,
    ):
        source_link = (
            MangaSourceLink.objects.get(
                manga=self.manga,
                provider="manga_plus",
            )
        )

        mock_sync.return_value = {
            "source_link": source_link,
            "latest_chapter": (
                SimpleNamespace(
                    number=Decimal("126")
                )
            ),
            "signal": SimpleNamespace(
                pending_chapters=Decimal("24")
            ),
            "used_fallback": False,
        }

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                (
                    "manga_insights:"
                    "sync_manga_source_now"
                ),
                kwargs={
                    "mal_id": self.manga.mal_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        mock_sync.assert_called_once_with(
            self.manga
        )


class MangaSourceSearchServiceTests(
    TestCase
):
    def setUp(self):
        self.manga = MangaEntry.objects.create(
            mal_id=162479,
            title="Kagurabachi",
            title_japanese="カグラバチ",
            list_status="reading",
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_search."
            "build_provider_client"
        )
    )
    def test_direct_url_scores_against_manga_title(
        self,
        mock_build_client,
    ):
        client = Mock()
        client.search.return_value = [
            SimpleNamespace(
                source_id="100274",
                title="Kagurabachi",
                url=(
                    "https://"
                    "mangaplus.shueisha.co.jp/"
                    "titles/100274"
                ),
                thumbnail_url=None,
            )
        ]

        mock_build_client.return_value = (
            client
        )

        result = search_manga_sources(
            self.manga,
            provider="manga_plus",
            query=(
                "https://"
                "mangaplus.shueisha.co.jp/"
                "titles/100274"
            ),
        )

        self.assertEqual(
            len(result.candidates),
            1,
        )
        self.assertEqual(
            result.candidates[0].score,
            Decimal("100.00"),
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_search."
            "build_provider_client"
        )
    )
    def test_candidates_are_ranked(
        self,
        mock_build_client,
    ):
        client = Mock()
        client.search.return_value = [
            SimpleNamespace(
                source_id="WRONG",
                title="Blue Lock",
                url=(
                    "https://example.test/"
                    "wrong"
                ),
                thumbnail_url=None,
            ),
            SimpleNamespace(
                source_id="RIGHT",
                title="Kagurabachi",
                url=(
                    "https://example.test/"
                    "right"
                ),
                thumbnail_url=None,
            ),
        ]

        mock_build_client.return_value = (
            client
        )

        result = search_manga_sources(
            self.manga,
            provider="weeb_central",
        )

        self.assertEqual(
            result.candidates[0].source_id,
            "RIGHT",
        )
        self.assertEqual(
            result.candidates[0].position,
            1,
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_search."
            "build_provider_client"
        )
    )
    def test_saving_manga_plus_marks_official(
        self,
        mock_build_client,
    ):
        client = Mock()
        client.search.return_value = [
            SimpleNamespace(
                source_id="100274",
                title="Kagurabachi",
                url=(
                    "https://"
                    "mangaplus.shueisha.co.jp/"
                    "titles/100274"
                ),
                thumbnail_url=None,
            )
        ]

        mock_build_client.return_value = (
            client
        )

        result = search_manga_sources(
            self.manga,
            provider="manga_plus",
            query="100274",
        )

        candidate = (
            get_candidate_by_source_id(
                result,
                "100274",
            )
        )

        source_link, created = (
            save_manga_source_candidate(
                self.manga,
                provider="manga_plus",
                candidate=candidate,
                search_query=result.query,
                priority=1,
            )
        )

        self.assertTrue(created)
        self.assertTrue(
            source_link.is_official
        )
        self.assertEqual(
            source_link.priority,
            1,
        )
        self.assertEqual(
            source_link.match_score,
            Decimal("100.00"),
        )

    @patch(
        (
            "mal_data.services."
            "manga_source_search."
            "build_provider_client"
        )
    )
    def test_unspecified_priority_is_preserved(
        self,
        mock_build_client,
    ):
        MangaSourceLink.objects.create(
            manga=self.manga,
            provider="weeb_central",
            source_id="OLD",
            source_title="Old Result",
            source_url=(
                "https://example.test/old"
            ),
            priority=2,
        )

        client = Mock()
        client.search.return_value = [
            SimpleNamespace(
                source_id="NEW",
                title="Kagurabachi",
                url=(
                    "https://example.test/new"
                ),
                thumbnail_url=None,
            )
        ]

        mock_build_client.return_value = (
            client
        )

        result = search_manga_sources(
            self.manga,
            provider="weeb_central",
        )

        source_link, created = (
            save_manga_source_candidate(
                self.manga,
                provider="weeb_central",
                candidate=(
                    result.candidates[0]
                ),
                search_query=result.query,
            )
        )

        self.assertFalse(created)
        self.assertEqual(
            source_link.priority,
            2,
        )
        self.assertEqual(
            source_link.source_id,
            "NEW",
        )

    def test_primary_role_reorders_sources(
        self,
    ):
        weeb_link = (
            MangaSourceLink.objects.create(
                manga=self.manga,
                provider="weeb_central",
                source_id="WEEB",
                source_title="Kagurabachi",
                source_url=(
                    "https://weebcentral.com/"
                    "series/WEEB/Kagurabachi"
                ),
                priority=1,
            )
        )

        candidate = SimpleNamespace(
            source_id="100274",
            title="Kagurabachi",
            url=(
                "https://"
                "mangaplus.shueisha.co.jp/"
                "titles/100274"
            ),
            thumbnail_url=None,
            score=Decimal("100.00"),
        )

        manga_plus_link, created = (
            save_manga_source_candidate_with_role(
                self.manga,
                provider="manga_plus",
                candidate=candidate,
                search_query="100274",
                role="primary",
            )
        )

        self.assertTrue(created)

        weeb_link.refresh_from_db()

        self.assertEqual(
            manga_plus_link.priority,
            1,
        )
        self.assertEqual(
            weeb_link.priority,
            2,
        )


class MangaSourceManagementServiceTests(
    TestCase
):
    def setUp(self):
        self.manga = MangaEntry.objects.create(
            mal_id=8001,
            title="Source Management Manga",
            list_status="reading",
        )

        self.manga_plus = (
            MangaSourceLink.objects.create(
                manga=self.manga,
                provider="manga_plus",
                source_id="MP",
                source_title="Manga Plus",
                source_url=(
                    "https://"
                    "mangaplus.shueisha.co.jp/"
                    "titles/100001"
                ),
                priority=1,
                active=True,
            )
        )

        self.weeb_central = (
            MangaSourceLink.objects.create(
                manga=self.manga,
                provider="weeb_central",
                source_id="WC",
                source_title="Weeb Central",
                source_url=(
                    "https://weebcentral.com/"
                    "series/WC/Test"
                ),
                priority=2,
                active=True,
            )
        )

    def test_make_primary_reorders_sources(
        self,
    ):
        updated_source = (
            make_manga_source_primary(
                self.weeb_central
            )
        )

        self.manga_plus.refresh_from_db()

        self.assertEqual(
            updated_source.priority,
            1,
        )
        self.assertEqual(
            self.manga_plus.priority,
            2,
        )

    def test_make_primary_activates_source(
        self,
    ):
        self.weeb_central.active = False
        self.weeb_central.save(
            update_fields=[
                "active",
                "updated_at",
            ]
        )

        updated_source = (
            make_manga_source_primary(
                self.weeb_central
            )
        )

        self.assertTrue(
            updated_source.active
        )
        self.assertEqual(
            updated_source.priority,
            1,
        )

    def test_toggle_source_active(
        self,
    ):
        updated_source = (
            toggle_manga_source_active(
                self.manga_plus
            )
        )

        self.assertFalse(
            updated_source.active
        )

    def test_unlink_compacts_priorities(
        self,
    ):
        unlink_manga_source(
            self.manga_plus
        )

        self.weeb_central.refresh_from_db()

        self.assertEqual(
            self.weeb_central.priority,
            1,
        )

        self.assertFalse(
            MangaSourceLink.objects
            .filter(
                pk=self.manga_plus.pk
            )
            .exists()
        )


