import requests
from datetime import date

from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import (
    ValidationError,
)
from django.db import (
    IntegrityError,
    transaction,
)

from django.db.models.deletion import (
    ProtectedError,
)

from django.contrib.auth import (
    get_user_model,
)

from django.test import (
    TestCase,
    SimpleTestCase,
    override_settings,
)


from .models import (
    Franchise,
    FranchiseMembership,
    MediaWork,
    Season,
    SeasonProgress,
    ViewingRun,
    WatchEntry,
)

from .forms import (
    ManualMediaWorkOwnerForm,
    NewViewingRunOwnerForm,
    SeasonOwnerForm,
    SeasonProgressOwnerForm,
    WatchEntryOwnerForm,
    TMDBImportForm,
    FranchiseMembershipOwnerForm,
    FranchiseOwnerForm,
)

from unittest.mock import (
    Mock,
    patch,
)

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
    normalize_collection_details,
)

from watchroom.services.tmdb_importer import (
    TMDBDuplicateWorkError,
    TMDBImportError,
    fetch_tmdb_details,
    import_tmdb_work,
)

from watchroom.services.tmdb_refresh import (
    TMDBRefreshError,
    TMDBRefreshResult,
    refresh_work_from_tmdb,
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




class WatchroomMediaWorkTests(TestCase):
    def test_movie_can_store_runtime(self):
        movie = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="Saw",
            presentation=(
                MediaWork.Presentation.LIVE_ACTION
            ),
            runtime_minutes=103,
        )

        self.assertEqual(
            movie.runtime_minutes,
            103,
        )
        self.assertEqual(
            movie.slug,
            "saw",
        )

    def test_series_rejects_runtime(self):
        series = MediaWork(
            media_type=(
                MediaWork.MediaType.SERIES
            ),
            title="Phineas and Ferb",
            presentation=(
                MediaWork.Presentation.ANIMATION
            ),
            runtime_minutes=22,
        )

        with self.assertRaises(
            ValidationError
        ):
            series.full_clean()

    def test_tmdb_identity_is_unique_per_type(
        self,
    ):
        MediaWork.objects.create(
            tmdb_id=100,
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="Example Movie",
        )

        MediaWork.objects.create(
            tmdb_id=100,
            media_type=(
                MediaWork.MediaType.SERIES
            ),
            title="Example Series",
        )

        self.assertEqual(
            MediaWork.objects.filter(
                tmdb_id=100,
            ).count(),
            2,
        )

    def test_duplicate_tmdb_identity_is_rejected(
        self,
    ):
        MediaWork.objects.create(
            tmdb_id=200,
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="First Movie",
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                MediaWork.objects.create(
                    tmdb_id=200,
                    media_type=(
                        MediaWork.MediaType.MOVIE
                    ),
                    title="Duplicate Movie",
                )

    def test_slug_is_unique_and_stable(self):
        first_work = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="The Purge",
        )
        second_work = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="The Purge",
        )

        self.assertEqual(
            first_work.slug,
            "the-purge",
        )
        self.assertEqual(
            second_work.slug,
            "the-purge-2",
        )

        original_slug = first_work.slug

        first_work.title = (
            "The Purge: Original Title"
        )
        first_work.save()

        self.assertEqual(
            first_work.slug,
            original_slug,
        )


class WatchroomFranchiseTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.series = (
            MediaWork.objects.create(
                media_type=(
                    MediaWork.MediaType
                    .SERIES
                ),
                title=(
                    "Phineas and Ferb"
                ),
                presentation=(
                    MediaWork.Presentation
                    .ANIMATION
                ),
            )
        )
        cls.movie = (
            MediaWork.objects.create(
                media_type=(
                    MediaWork.MediaType
                    .MOVIE
                ),
                title=(
                    "Phineas and Ferb "
                    "the Movie"
                ),
                presentation=(
                    MediaWork.Presentation
                    .ANIMATION
                ),
                runtime_minutes=78,
            )
        )

    def test_franchise_slug_is_unique_and_stable(
        self,
    ):
        first = Franchise.objects.create(
            name="Saw",
        )
        second = (
            Franchise.objects.create(
                name="Saw",
            )
        )

        self.assertEqual(
            first.slug,
            "saw",
        )
        self.assertEqual(
            second.slug,
            "saw-2",
        )

        original_slug = first.slug
        first.name = "Saw Franchise"
        first.save()

        self.assertEqual(
            first.slug,
            original_slug,
        )

    def test_tmdb_collection_identity_is_unique(
        self,
    ):
        Franchise.objects.create(
            name="Saw",
            tmdb_collection_id=656,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                Franchise.objects.create(
                    name="Duplicate Saw",
                    tmdb_collection_id=656,
                )

    def test_franchise_accepts_movies_and_series(
        self,
    ):
        franchise = (
            Franchise.objects.create(
                name="Phineas and Ferb",
            )
        )

        FranchiseMembership.objects.create(
            franchise=franchise,
            media_work=self.series,
            position=1,
            role=(
                FranchiseMembership
                .Role.MAIN
            ),
        )
        FranchiseMembership.objects.create(
            franchise=franchise,
            media_work=self.movie,
            position=2,
            role=(
                FranchiseMembership
                .Role.MAIN
            ),
        )

        self.assertEqual(
            franchise.works.count(),
            2,
        )
        self.assertTrue(
            franchise.works.filter(
                media_type="series",
            ).exists()
        )
        self.assertTrue(
            franchise.works.filter(
                media_type="movie",
            ).exists()
        )

    def test_work_is_unique_inside_franchise(
        self,
    ):
        franchise = (
            Franchise.objects.create(
                name="Phineas and Ferb",
            )
        )

        FranchiseMembership.objects.create(
            franchise=franchise,
            media_work=self.series,
            position=1,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                FranchiseMembership.objects.create(
                    franchise=franchise,
                    media_work=self.series,
                    position=2,
                )

    def test_work_can_belong_to_multiple_franchises(
        self,
    ):
        main_franchise = (
            Franchise.objects.create(
                name="Phineas and Ferb",
            )
        )
        disney_movies = (
            Franchise.objects.create(
                name="Disney Movies",
            )
        )

        FranchiseMembership.objects.create(
            franchise=main_franchise,
            media_work=self.movie,
            position=2,
        )
        FranchiseMembership.objects.create(
            franchise=disney_movies,
            media_work=self.movie,
            position=1,
        )

        self.assertEqual(
            self.movie.franchises.count(),
            2,
        )

    def test_membership_position_must_be_positive(
        self,
    ):
        franchise = (
            Franchise.objects.create(
                name="Invalid Position",
            )
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                FranchiseMembership.objects.create(
                    franchise=franchise,
                    media_work=self.movie,
                    position=0,
                )

    def test_deleting_franchise_preserves_works(
        self,
    ):
        franchise = (
            Franchise.objects.create(
                name="Phineas and Ferb",
            )
        )
        membership = (
            FranchiseMembership
            .objects.create(
                franchise=franchise,
                media_work=self.series,
                position=1,
            )
        )

        franchise.delete()

        self.assertTrue(
            MediaWork.objects.filter(
                pk=self.series.pk,
            ).exists()
        )
        self.assertFalse(
            FranchiseMembership
            .objects.filter(
                pk=membership.pk,
            )
            .exists()
        )

    def test_deleting_work_removes_membership(
        self,
    ):
        franchise = (
            Franchise.objects.create(
                name="Phineas and Ferb",
            )
        )
        membership = (
            FranchiseMembership
            .objects.create(
                franchise=franchise,
                media_work=self.movie,
                position=1,
            )
        )

        movie_pk = self.movie.pk
        self.movie.delete()

        self.assertTrue(
            Franchise.objects.filter(
                pk=franchise.pk,
            ).exists()
        )
        self.assertFalse(
            MediaWork.objects.filter(
                pk=movie_pk,
            ).exists()
        )
        self.assertFalse(
            FranchiseMembership
            .objects.filter(
                pk=membership.pk,
            )
            .exists()
        )


class WatchroomSeasonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.series = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.SERIES
            ),
            title="Phineas and Ferb",
            presentation=(
                MediaWork.Presentation.ANIMATION
            ),
        )
        cls.movie = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="Saw",
            presentation=(
                MediaWork.Presentation.LIVE_ACTION
            ),
        )

    def test_series_can_have_season(self):
        season = Season(
            media_work=self.series,
            season_number=1,
            name="Season 1",
            episode_count=38,
        )

        season.full_clean()
        season.save()

        self.assertEqual(
            season.episode_count,
            38,
        )
        self.assertFalse(
            season.is_special
        )

    def test_movie_rejects_season(self):
        season = Season(
            media_work=self.movie,
            season_number=1,
            episode_count=1,
        )

        with self.assertRaises(
            ValidationError
        ):
            season.full_clean()

    def test_season_number_is_unique_per_series(
        self,
    ):
        Season.objects.create(
            media_work=self.series,
            season_number=1,
            episode_count=38,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                Season.objects.create(
                    media_work=self.series,
                    season_number=1,
                    episode_count=39,
                )

    def test_season_zero_represents_specials(
        self,
    ):
        specials = Season.objects.create(
            media_work=self.series,
            season_number=0,
            name="Specials",
            episode_count=4,
        )

        self.assertTrue(
            specials.is_special
        )
        self.assertEqual(
            str(specials),
            "Phineas and Ferb — Specials",
        )

    def test_same_season_number_is_allowed_for_different_series(
        self,
    ):
        other_series = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.SERIES
            ),
            title="The Amazing World of Gumball",
            presentation=(
                MediaWork.Presentation.ANIMATION
            ),
        )

        Season.objects.create(
            media_work=self.series,
            season_number=1,
            episode_count=38,
        )
        Season.objects.create(
            media_work=other_series,
            season_number=1,
            episode_count=36,
        )

        self.assertEqual(
            Season.objects.filter(
                season_number=1,
            ).count(),
            2,
        )


class WatchroomWatchEntryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.work = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.SERIES
            ),
            title="Wizards of Waverly Place",
            presentation=(
                MediaWork.Presentation.LIVE_ACTION
            ),
        )

    def test_default_status_is_plan_to_watch(
        self,
    ):
        entry = WatchEntry.objects.create(
            media_work=self.work,
        )

        self.assertEqual(
            entry.status,
            WatchEntry.Status.PLAN_TO_WATCH,
        )

    def test_work_can_only_have_one_entry(self):
        WatchEntry.objects.create(
            media_work=self.work,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                WatchEntry.objects.create(
                    media_work=self.work,
                    status=(
                        WatchEntry.Status.WATCHING
                    ),
                )


class WatchroomViewingRunTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.movie = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="Saw",
            presentation=(
                MediaWork.Presentation.LIVE_ACTION
            ),
            runtime_minutes=103,
        )
        cls.movie_entry = (
            WatchEntry.objects.create(
                media_work=cls.movie,
            )
        )

        cls.series = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.SERIES
            ),
            title="Phineas and Ferb",
            presentation=(
                MediaWork.Presentation.ANIMATION
            ),
        )
        cls.series_entry = (
            WatchEntry.objects.create(
                media_work=cls.series,
            )
        )

    def test_movie_run_can_store_progress_minutes(
        self,
    ):
        run = ViewingRun(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.PAUSED,
            progress_minutes=54,
        )

        run.full_clean()
        run.save()

        self.assertEqual(
            run.progress_minutes,
            54,
        )
        self.assertTrue(
            run.is_active
        )

    def test_series_run_rejects_progress_minutes(
        self,
    ):
        run = ViewingRun(
            watch_entry=self.series_entry,
            number=1,
            progress_minutes=22,
        )

        with self.assertRaises(
            ValidationError
        ):
            run.full_clean()

    def test_movie_progress_cannot_exceed_runtime(
        self,
    ):
        run = ViewingRun(
            watch_entry=self.movie_entry,
            number=1,
            progress_minutes=104,
        )

        with self.assertRaises(
            ValidationError
        ):
            run.full_clean()

    def test_finish_date_cannot_precede_start_date(
        self,
    ):
        run = ViewingRun(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.COMPLETED,
            started_on=date(
                2026,
                7,
                24,
            ),
            finished_on=date(
                2026,
                7,
                23,
            ),
        )

        with self.assertRaises(
            ValidationError
        ):
            run.full_clean()

    def test_run_number_is_unique_per_entry(
        self,
    ):
        ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.COMPLETED,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                ViewingRun.objects.create(
                    watch_entry=self.movie_entry,
                    number=1,
                    status=(
                        ViewingRun.Status.DROPPED
                    ),
                )

    def test_entry_cannot_have_two_active_runs(
        self,
    ):
        ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.PAUSED,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                ViewingRun.objects.create(
                    watch_entry=self.movie_entry,
                    number=2,
                    status=(
                        ViewingRun.Status.WATCHING
                    ),
                )

    def test_completed_run_can_coexist_with_rewatch(
        self,
    ):
        first_run = ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.COMPLETED,
        )
        second_run = ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=2,
            status=ViewingRun.Status.WATCHING,
        )

        self.assertFalse(
            first_run.is_rewatch
        )
        self.assertTrue(
            second_run.is_rewatch
        )
        self.assertTrue(
            second_run.is_active
        )

    def test_active_run_rejects_finish_date(
        self,
    ):
        run = ViewingRun(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
            finished_on=date(
                2026,
                7,
                24,
            ),
        )

        with self.assertRaises(
            ValidationError
        ):
            run.full_clean()


class WatchroomSeasonProgressTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.series = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.SERIES
            ),
            title="Phineas and Ferb",
            presentation=(
                MediaWork.Presentation.ANIMATION
            ),
        )
        cls.series_entry = (
            WatchEntry.objects.create(
                media_work=cls.series,
                status=(
                    WatchEntry.Status.WATCHING
                ),
            )
        )
        cls.series_run = (
            ViewingRun.objects.create(
                watch_entry=cls.series_entry,
                number=1,
                status=(
                    ViewingRun.Status.WATCHING
                ),
            )
        )
        cls.season = Season.objects.create(
            media_work=cls.series,
            season_number=1,
            name="Season 1",
            episode_count=38,
        )
        cls.specials = Season.objects.create(
            media_work=cls.series,
            season_number=0,
            name="Specials",
            episode_count=4,
        )

        cls.other_series = (
            MediaWork.objects.create(
                media_type=(
                    MediaWork.MediaType.SERIES
                ),
                title=(
                    "The Amazing World of Gumball"
                ),
                presentation=(
                    MediaWork.Presentation.ANIMATION
                ),
            )
        )
        cls.other_season = (
            Season.objects.create(
                media_work=cls.other_series,
                season_number=1,
                episode_count=36,
            )
        )

        cls.movie = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="Saw",
            runtime_minutes=103,
        )
        cls.movie_entry = (
            WatchEntry.objects.create(
                media_work=cls.movie,
            )
        )
        cls.movie_run = ViewingRun.objects.create(
            watch_entry=cls.movie_entry,
            number=1,
            status=ViewingRun.Status.PAUSED,
        )

    def test_series_run_can_store_progress(
        self,
    ):
        progress = SeasonProgress(
            viewing_run=self.series_run,
            season=self.season,
            episodes_watched=12,
        )

        progress.full_clean()
        progress.save()

        self.assertEqual(
            progress.display_progress,
            "12 / 38",
        )
        self.assertFalse(
            progress.is_complete
        )

    def test_movie_run_rejects_season_progress(
        self,
    ):
        progress = SeasonProgress(
            viewing_run=self.movie_run,
            season=self.season,
            episodes_watched=1,
        )

        with self.assertRaises(
            ValidationError
        ):
            progress.full_clean()

    def test_progress_rejects_other_series_season(
        self,
    ):
        progress = SeasonProgress(
            viewing_run=self.series_run,
            season=self.other_season,
            episodes_watched=1,
        )

        with self.assertRaises(
            ValidationError
        ):
            progress.full_clean()

    def test_progress_cannot_exceed_episode_count(
        self,
    ):
        progress = SeasonProgress(
            viewing_run=self.series_run,
            season=self.season,
            episodes_watched=39,
        )

        with self.assertRaises(
            ValidationError
        ):
            progress.full_clean()

    def test_season_progress_only_stores_episode_count(
        self,
    ):
        progress = SeasonProgress.objects.create(
            viewing_run=self.series_run,
            season=self.season,
            episodes_watched=12,
        )

        self.assertEqual(
            progress.display_progress,
            "12 / 38",
        )

    def test_same_season_is_unique_per_run(
        self,
    ):
        SeasonProgress.objects.create(
            viewing_run=self.series_run,
            season=self.season,
            episodes_watched=12,
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                SeasonProgress.objects.create(
                    viewing_run=self.series_run,
                    season=self.season,
                    episodes_watched=13,
                )

    def test_rewatch_has_independent_progress(
        self,
    ):
        SeasonProgress.objects.create(
            viewing_run=self.series_run,
            season=self.season,
            episodes_watched=38,
        )

        self.series_run.status = (
            ViewingRun.Status.COMPLETED
        )
        self.series_run.save(
            update_fields=[
                "status",
            ]
        )

        rewatch = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=2,
            status=ViewingRun.Status.WATCHING,
        )
        rewatch_progress = (
            SeasonProgress.objects.create(
                viewing_run=rewatch,
                season=self.season,
                episodes_watched=12,
            )
        )

        self.assertEqual(
            SeasonProgress.objects.filter(
                season=self.season,
            ).count(),
            2,
        )
        self.assertEqual(
            rewatch_progress.display_progress,
            "12 / 38",
        )

    def test_season_with_history_is_protected(
        self,
    ):
        SeasonProgress.objects.create(
            viewing_run=self.series_run,
            season=self.season,
            episodes_watched=12,
        )

        with self.assertRaises(
            ProtectedError
        ):
            self.season.delete()


class WatchroomPublicDashboardTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.movie = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="Saw",
            presentation=(
                MediaWork.Presentation.LIVE_ACTION
            ),
            runtime_minutes=103,
        )
        cls.movie_entry = (
            WatchEntry.objects.create(
                media_work=cls.movie,
                status=(
                    WatchEntry.Status.PLAN_TO_WATCH
                ),
            )
        )

        cls.series = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.SERIES
            ),
            title="Phineas and Ferb",
            presentation=(
                MediaWork.Presentation.ANIMATION
            ),
        )
        cls.series_entry = (
            WatchEntry.objects.create(
                media_work=cls.series,
                status=(
                    WatchEntry.Status.WATCHING
                ),
            )
        )
        cls.series_run = ViewingRun.objects.create(
            watch_entry=cls.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )
        cls.season = Season.objects.create(
            media_work=cls.series,
            season_number=1,
            episode_count=38,
        )
        SeasonProgress.objects.create(
            viewing_run=cls.series_run,
            season=cls.season,
            episodes_watched=12,
        )

    def test_dashboard_is_public(self):
        response = self.client.get(
            reverse(
                "watchroom:dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "watchroom/dashboard.html",
        )

    def test_dashboard_shows_summary_counts(
        self,
    ):
        response = self.client.get(
            reverse(
                "watchroom:dashboard"
            )
        )

        self.assertEqual(
            response.context["total_count"],
            2,
        )
        self.assertEqual(
            response.context["movie_count"],
            1,
        )
        self.assertEqual(
            response.context["series_count"],
            1,
        )
        self.assertEqual(
            response.context["watching_count"],
            1,
        )

    def test_dashboard_shows_series_progress(
        self,
    ):
        response = self.client.get(
            reverse(
                "watchroom:dashboard"
            )
        )

        self.assertContains(
            response,
            "Season 1 · 12 / 38",
        )
        self.assertContains(
            response,
            "Phineas and Ferb",
        )

    def test_dashboard_shows_tmdb_attribution(
        self,
    ):
        response = self.client.get(
            reverse(
                "watchroom:dashboard"
            )
        )

        self.assertContains(
            response,
            (
                "<p>"
                "This product uses the TMDB API "
                "but is not endorsed or certified "
                "by TMDB."
                "</p>"
            ),
            html=True,
        )

    def test_home_links_to_watchroom(
        self,
    ):
        response = self.client.get(
            reverse("core:home")
        )

        self.assertContains(
            response,
            reverse(
                "watchroom:dashboard"
            ),
        )
        self.assertContains(
            response,
            "Local-first media library",
        )


class WatchroomPublicLibraryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.movie = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="Saw",
            original_title="Saw",
            presentation=(
                MediaWork.Presentation.LIVE_ACTION
            ),
            runtime_minutes=103,
        )
        cls.movie_entry = (
            WatchEntry.objects.create(
                media_work=cls.movie,
                status=(
                    WatchEntry.Status
                    .PLAN_TO_WATCH
                ),
            )
        )

        cls.series = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.SERIES
            ),
            title="Phineas and Ferb",
            presentation=(
                MediaWork.Presentation.ANIMATION
            ),
        )
        cls.series_entry = (
            WatchEntry.objects.create(
                media_work=cls.series,
                status=(
                    WatchEntry.Status.WATCHING
                ),
            )
        )
        cls.series_run = (
            ViewingRun.objects.create(
                watch_entry=cls.series_entry,
                number=1,
                status=(
                    ViewingRun.Status.WATCHING
                ),
            )
        )
        cls.season = Season.objects.create(
            media_work=cls.series,
            season_number=1,
            name="Season 1",
            episode_count=38,
        )
        cls.specials = Season.objects.create(
            media_work=cls.series,
            season_number=0,
            name="Specials",
            episode_count=4,
        )
        SeasonProgress.objects.create(
            viewing_run=cls.series_run,
            season=cls.season,
            episodes_watched=12,
        )

        cls.completed_work = (
            MediaWork.objects.create(
                media_type=(
                    MediaWork.MediaType.SERIES
                ),
                title=(
                    "Wizards of Waverly Place"
                ),
                presentation=(
                    MediaWork.Presentation
                    .LIVE_ACTION
                ),
            )
        )
        cls.completed_entry = (
            WatchEntry.objects.create(
                media_work=cls.completed_work,
                status=(
                    WatchEntry.Status.COMPLETED
                ),
            )
        )
        ViewingRun.objects.create(
            watch_entry=cls.completed_entry,
            number=1,
            status=(
                ViewingRun.Status.COMPLETED
            ),
        )
        ViewingRun.objects.create(
            watch_entry=cls.completed_entry,
            number=2,
            status=(
                ViewingRun.Status.WATCHING
            ),
        )

    def test_library_is_public(self):
        response = self.client.get(
            reverse("watchroom:library")
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "watchroom/library.html",
        )

    def test_library_searches_by_title(self):
        response = self.client.get(
            reverse("watchroom:library"),
            {
                "q": "Phineas",
            },
        )

        self.assertContains(
            response,
            "Phineas and Ferb",
        )
        self.assertNotContains(
            response,
            ">Saw<",
            html=True,
        )

    def test_library_filters_by_type(self):
        response = self.client.get(
            reverse("watchroom:library"),
            {
                "type": "movie",
            },
        )

        self.assertEqual(
            response.context["result_count"],
            1,
        )
        self.assertContains(
            response,
            "Saw",
        )

    def test_library_filters_by_presentation(
        self,
    ):
        response = self.client.get(
            reverse("watchroom:library"),
            {
                "presentation": "animation",
            },
        )

        self.assertEqual(
            response.context["result_count"],
            1,
        )
        self.assertContains(
            response,
            "Phineas and Ferb",
        )

    def test_library_filters_rewatching(self):
        response = self.client.get(
            reverse("watchroom:library"),
            {
                "activity": "rewatching",
            },
        )

        self.assertEqual(
            response.context["result_count"],
            1,
        )
        self.assertContains(
            response,
            "Wizards of Waverly Place",
        )
        self.assertContains(
            response,
            "Rewatching",
        )

    def test_library_links_to_detail(self):
        response = self.client.get(
            reverse("watchroom:library")
        )

        self.assertContains(
            response,
            self.series.get_absolute_url(),
        )

    def test_series_detail_is_public(self):
        response = self.client.get(
            self.series.get_absolute_url()
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "watchroom/detail.html",
        )
        self.assertContains(
            response,
            "Season 1",
        )
        self.assertContains(
            response,
            "12",
        )
        self.assertContains(
            response,
            "38",
        )
        self.assertContains(
            response,
            "Specials",
        )

    def test_movie_detail_shows_runtime(self):
        response = self.client.get(
            self.movie.get_absolute_url()
        )

        self.assertContains(
            response,
            "103",
        )
        self.assertContains(
            response,
            "Runtime",
        )

    def test_missing_detail_returns_404(self):
        response = self.client.get(
            reverse(
                "watchroom:detail",
                kwargs={
                    "slug": "missing-work",
                },
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )


class WatchroomOwnerFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.movie = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="Saw",
            runtime_minutes=103,
        )
        cls.movie_entry = (
            WatchEntry.objects.create(
                media_work=cls.movie,
            )
        )

        cls.series = MediaWork.objects.create(
            media_type=(
                MediaWork.MediaType.SERIES
            ),
            title="Phineas and Ferb",
            presentation=(
                MediaWork.Presentation.ANIMATION
            ),
        )
        cls.series_entry = (
            WatchEntry.objects.create(
                media_work=cls.series,
            )
        )
        cls.season = Season.objects.create(
            media_work=cls.series,
            season_number=1,
            episode_count=38,
        )

    def test_manual_movie_form_accepts_runtime(
        self,
    ):
        form = ManualMediaWorkOwnerForm(
            data={
                "media_type": "movie",
                "title": "The Purge",
                "original_title": "",
                "presentation": "live_action",
                "overview": "",
                "original_language": "en",
                "first_release_date": "",
                "runtime_minutes": 90,
                "external_status": "",
                "poster_url": "",
                "backdrop_url": "",
                "status": "plan_to_watch",
                "notes": "",
            },
        )

        self.assertTrue(
            form.is_valid(),
            form.errors,
        )

    def test_manual_series_form_rejects_runtime(
        self,
    ):
        form = ManualMediaWorkOwnerForm(
            data={
                "media_type": "series",
                "title": "Example Series",
                "original_title": "",
                "presentation": "live_action",
                "overview": "",
                "original_language": "en",
                "first_release_date": "",
                "runtime_minutes": 22,
                "external_status": "",
                "poster_url": "",
                "backdrop_url": "",
                "status": "plan_to_watch",
                "notes": "",
            },
        )

        self.assertFalse(
            form.is_valid()
        )
        self.assertIn(
            "runtime_minutes",
            form.errors,
        )

    def test_entry_form_rejects_watching_without_run(
        self,
    ):
        form = WatchEntryOwnerForm(
            data={
                "status": "watching",
                "notes": "",
            },
            instance=self.movie_entry,
        )

        self.assertFalse(
            form.is_valid()
        )
        self.assertIn(
            "status",
            form.errors,
        )

    def test_entry_status_is_disabled_with_history(
        self,
    ):
        ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=(
                ViewingRun.Status.COMPLETED
            ),
        )

        form = WatchEntryOwnerForm(
            instance=self.movie_entry,
        )

        self.assertTrue(
            form.fields["status"].disabled
        )

    def test_season_form_assigns_parent_series(
        self,
    ):
        form = SeasonOwnerForm(
            data={
                "season_number": 2,
                "name": "Season 2",
                "episode_count": 39,
                "air_date": "",
                "poster_url": "",
            },
            media_work=self.series,
        )

        self.assertTrue(
            form.is_valid(),
            form.errors,
        )

        season = form.save(
            commit=False
        )

        self.assertEqual(
            season.media_work,
            self.series,
        )

    def test_new_run_form_rejects_second_active_run(
        self,
    ):
        ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=(
                ViewingRun.Status.PAUSED
            ),
        )

        form = NewViewingRunOwnerForm(
            data={
                "progress_minutes": "",
                "notes": "",
            },
            watch_entry=self.movie_entry,
        )

        self.assertFalse(
            form.is_valid()
        )
        self.assertTrue(
            form.non_field_errors()
        )

    def test_series_run_form_disables_minutes(
        self,
    ):
        form = NewViewingRunOwnerForm(
            watch_entry=self.series_entry,
        )

        self.assertTrue(
            form.fields[
                "progress_minutes"
            ].disabled
        )

    def test_season_progress_form_enforces_total(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=(
                ViewingRun.Status.WATCHING
            ),
        )

        form = SeasonProgressOwnerForm(
            data={
                "episodes_watched": 39,
            },
            viewing_run=run,
            season=self.season,
        )

        self.assertFalse(
            form.is_valid()
        )
        self.assertIn(
            "episodes_watched",
            form.errors,
        )

    def test_season_progress_form_only_exposes_count(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        form = SeasonProgressOwnerForm(
            viewing_run=run,
            season=self.season,
        )

        self.assertEqual(
            list(form.fields),
            [
                "episodes_watched",
            ],
        )


class WatchroomOwnerWorkflowTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects.create_user(
                username="watchroom-owner",
                password="test-password",
            )
        )

        cls.movie = MediaWork.objects.create(
            media_type="movie",
            title="Saw",
            runtime_minutes=103,
        )
        cls.movie_entry = (
            WatchEntry.objects.create(
                media_work=cls.movie,
            )
        )

        cls.series = MediaWork.objects.create(
            media_type="series",
            title="Phineas and Ferb",
            presentation="animation",
        )
        cls.series_entry = (
            WatchEntry.objects.create(
                media_work=cls.series,
            )
        )
        cls.season = Season.objects.create(
            media_work=cls.series,
            season_number=1,
            episode_count=38,
        )

    def manual_work_payload(
        self,
        *,
        title="The Purge",
        status="plan_to_watch",
    ):
        return {
            "media_type": "movie",
            "title": title,
            "original_title": "",
            "presentation": "live_action",
            "overview": "",
            "original_language": "en",
            "first_release_date": "",
            "runtime_minutes": 90,
            "external_status": "",
            "poster_url": "",
            "backdrop_url": "",
            "status": status,
            "notes": "",
        }

    def test_create_work_requires_login(self):
        response = self.client.get(
            reverse(
                "watchroom:create_work"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_owner_can_create_manual_work(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:create_work"
            ),
            self.manual_work_payload(),
        )

        work = MediaWork.objects.get(
            title="The Purge"
        )

        self.assertRedirects(
            response,
            work.get_absolute_url(),
        )
        self.assertTrue(
            WatchEntry.objects.filter(
                media_work=work,
                status="plan_to_watch",
            ).exists()
        )

    def test_completed_manual_work_creates_run(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:create_work"
            ),
            self.manual_work_payload(
                title="Completed Movie",
                status="completed",
            ),
        )

        entry = WatchEntry.objects.get(
            media_work__title=(
                "Completed Movie"
            )
        )

        self.assertTrue(
            ViewingRun.objects.filter(
                watch_entry=entry,
                number=1,
                status="completed",
            ).exists()
        )

    def test_entry_update_is_post_only(self):
        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            reverse(
                "watchroom:update_entry",
                kwargs={
                    "slug": self.movie.slug,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    def test_owner_can_update_entry(self):
        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:update_entry",
                kwargs={
                    "slug": self.movie.slug,
                },
            ),
            {
                "entry-status": "dropped",
                "entry-notes": (
                    "Stopped for now."
                ),
            },
        )

        self.movie_entry.refresh_from_db()

        self.assertEqual(
            self.movie_entry.status,
            "dropped",
        )
        self.assertEqual(
            self.movie_entry.notes,
            "Stopped for now.",
        )

    def test_owner_can_create_season(self):
        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:create_season",
                kwargs={
                    "slug": self.series.slug,
                },
            ),
            {
                "new-season-season_number": 2,
                "new-season-name": "Season 2",
                "new-season-episode_count": 39,
                "new-season-air_date": "",
                "new-season-poster_url": "",
            },
        )

        self.assertTrue(
            Season.objects.filter(
                media_work=self.series,
                season_number=2,
                episode_count=39,
            ).exists()
        )

    def test_season_count_cannot_drop_below_progress(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status="watching",
        )
        SeasonProgress.objects.create(
            viewing_run=run,
            season=self.season,
            episodes_watched=12,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:update_season",
                kwargs={
                    "slug": self.series.slug,
                    "season_id": self.season.pk,
                },
            ),
            {
                (
                    f"season-{self.season.pk}"
                    "-season_number"
                ): 1,
                (
                    f"season-{self.season.pk}"
                    "-name"
                ): "Season 1",
                (
                    f"season-{self.season.pk}"
                    "-episode_count"
                ): 10,
                (
                    f"season-{self.season.pk}"
                    "-air_date"
                ): "",
                (
                    f"season-{self.season.pk}"
                    "-poster_url"
                ): "",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        rendered_season = next(
            season
            for season in response.context[
                "all_seasons"
            ]
            if season.pk == self.season.pk
        )

        self.assertIsNotNone(
            rendered_season.owner_form
        )
        self.assertIn(
            "episode_count",
            rendered_season.owner_form.errors,
        )
        self.assertEqual(
            rendered_season.owner_form.errors[
                "episode_count"
            ],
            [
                (
                    "Episode count cannot be lower "
                    "than the existing progress of 12."
                ),
            ],
        )

        self.season.refresh_from_db()

        self.assertEqual(
            self.season.episode_count,
            38,
        )

    def test_owner_can_delete_unused_season(
        self,
    ):
        unused = Season.objects.create(
            media_work=self.series,
            season_number=2,
            episode_count=10,
        )

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:delete_season",
                kwargs={
                    "slug": self.series.slug,
                    "season_id": unused.pk,
                },
            )
        )

        self.assertFalse(
            Season.objects.filter(
                pk=unused.pk,
            ).exists()
        )

    def test_season_with_progress_is_protected(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status="watching",
        )
        SeasonProgress.objects.create(
            viewing_run=run,
            season=self.season,
            episodes_watched=12,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:delete_season",
                kwargs={
                    "slug": self.series.slug,
                    "season_id": self.season.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            response.context[
                "season_action_error"
            ],
            (
                "This season cannot be deleted "
                "because viewing progress already "
                "references it."
            ),
        )
        self.assertEqual(
            response.context[
                "season_action_id"
            ],
            self.season.pk,
        )
        self.assertTrue(
            Season.objects.filter(
                pk=self.season.pk,
            ).exists()
        )

    def test_authenticated_library_renders(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            reverse("watchroom:library")
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            reverse(
                "watchroom:create_work"
            ),
        )

    def test_anonymous_detail_hides_owner_controls(
        self,
    ):
        response = self.client.get(
            self.movie.get_absolute_url()
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertNotContains(
            response,
            "Viewing Controls",
        )
        self.assertNotContains(
            response,
            "Start First Watch",
        )


    def test_owner_detail_shows_start_run_form(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            self.movie.get_absolute_url()
        )

        self.assertContains(
            response,
            "Viewing Controls",
        )
        self.assertContains(
            response,
            "Start First Watch",
        )
        self.assertContains(
            response,
            reverse(
                "watchroom:create_run",
                kwargs={
                    "slug": self.movie.slug,
                },
            ),
        )


    def test_owner_detail_shows_active_run_actions(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            self.movie.get_absolute_url()
        )

        self.assertContains(
            response,
            "Pause",
        )
        self.assertContains(
            response,
            "Complete",
        )
        self.assertContains(
            response,
            "Drop",
        )
        self.assertContains(
            response,
            reverse(
                "watchroom:update_run",
                kwargs={
                    "slug": self.movie.slug,
                    "run_id": run.pk,
                },
            ),
        )


    def test_owner_series_detail_shows_progress_forms(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            self.series.get_absolute_url()
        )

        self.assertContains(
            response,
            "Season Progress",
        )
        self.assertContains(
            response,
            "Save Progress",
        )
        self.assertContains(
            response,
            reverse(
                "watchroom:update_season_progress",
                kwargs={
                    "slug": self.series.slug,
                    "run_id": run.pk,
                    "season_id": self.season.pk,
                },
            ),
        )

        self.assertNotContains(
            response,
            "Movie Progress",
        )
        progress_prefix = (
            f"progress-{run.pk}-"
            f"{self.season.pk}"
        )

        self.assertContains(
            response,
            (
                f'name="{progress_prefix}-'
                'episodes_watched"'
            ),
        )

        self.assertNotContains(
            response,
            (
                f'name="{progress_prefix}-'
                'started_on"'
            ),
        )

        self.assertNotContains(
            response,
            (
                f'name="{progress_prefix}-'
                'finished_on"'
            ),
        )

        self.assertNotContains(
            response,
            "Optional dates",
        )


    def test_completed_series_detail_uses_latest_run_progress(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.COMPLETED,
        )
        SeasonProgress.objects.create(
            viewing_run=run,
            season=self.season,
            episodes_watched=38,
        )

        self.series_entry.status = (
            WatchEntry.Status.COMPLETED
        )
        self.series_entry.save()

        response = self.client.get(
            self.series.get_absolute_url()
        )

        rendered_season = (
            response.context[
                "regular_seasons"
            ][0]
        )

        self.assertIsNotNone(
            rendered_season.current_progress
        )
        self.assertEqual(
            (
                rendered_season
                .current_progress
                .episodes_watched
            ),
            38,
        )

    def test_full_progress_auto_completes_series_run(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:update_season_progress",
                kwargs={
                    "slug": self.series.slug,
                    "run_id": run.pk,
                    "season_id": self.season.pk,
                },
            ),
            {
                (
                    f"progress-{run.pk}-"
                    f"{self.season.pk}-"
                    "episodes_watched"
                ): 38,
                (
                    f"progress-{run.pk}-"
                    f"{self.season.pk}-"
                    "started_on"
                ): "",
                (
                    f"progress-{run.pk}-"
                    f"{self.season.pk}-"
                    "finished_on"
                ): "",
            },
        )

        run.refresh_from_db()
        self.series_entry.refresh_from_db()

        self.assertEqual(
            run.status,
            ViewingRun.Status.COMPLETED,
        )
        self.assertIsNotNone(
            run.finished_on
        )
        self.assertEqual(
            self.series_entry.status,
            WatchEntry.Status.COMPLETED,
        )


    def test_full_season_does_not_complete_when_another_is_pending(
        self,
    ):
        second_season = Season.objects.create(
            media_work=self.series,
            season_number=2,
            episode_count=20,
        )
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:update_season_progress",
                kwargs={
                    "slug": self.series.slug,
                    "run_id": run.pk,
                    "season_id": self.season.pk,
                },
            ),
            {
                (
                    f"progress-{run.pk}-"
                    f"{self.season.pk}-"
                    "episodes_watched"
                ): 38,
                (
                    f"progress-{run.pk}-"
                    f"{self.season.pk}-"
                    "started_on"
                ): "",
                (
                    f"progress-{run.pk}-"
                    f"{self.season.pk}-"
                    "finished_on"
                ): "",
            },
        )

        run.refresh_from_db()

        self.assertEqual(
            run.status,
            ViewingRun.Status.WATCHING,
        )
        self.assertFalse(
            SeasonProgress.objects.filter(
                viewing_run=run,
                season=second_season,
            ).exists()
        )
    def test_series_run_form_fields_render_once(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.COMPLETED,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            self.series.get_absolute_url()
        )

        prefix = f"run-{run.pk}"

        self.assertContains(
            response,
            f'name="{prefix}-started_on"',
            count=1,
        )
        self.assertContains(
            response,
            f'name="{prefix}-finished_on"',
            count=1,
        )
        self.assertContains(
            response,
            f'name="{prefix}-notes"',
            count=1,
        )
        self.assertNotContains(
            response,
            f'name="{prefix}-progress_minutes"',
        )

    def test_completed_series_progress_is_read_only(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.COMPLETED,
        )
        SeasonProgress.objects.create(
            viewing_run=run,
            season=self.season,
            episodes_watched=38,
        )

        self.series_entry.status = (
            WatchEntry.Status.COMPLETED
        )
        self.series_entry.save()

        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            self.series.get_absolute_url()
        )

        rendered_season = (
            response.context[
                "regular_seasons"
            ][0]
        )

        self.assertEqual(
            rendered_season
            .current_progress
            .episodes_watched,
            38,
        )
        self.assertIsNone(
            response.context["progress_run"]
        )
        self.assertContains(
            response,
            "Start Rewatch",
        )
        self.assertNotContains(
            response,
            reverse(
                "watchroom:update_season_progress",
                kwargs={
                    "slug": self.series.slug,
                    "run_id": run.pk,
                    "season_id": self.season.pk,
                },
            ),
        )

    def test_new_run_form_does_not_expose_start_date(
        self,
    ):
        form = NewViewingRunOwnerForm(
            watch_entry=self.series_entry,
        )

        self.assertNotIn(
            "started_on",
            form.fields,
        )

    def test_delete_work_requires_login(
        self,
    ):
        work = MediaWork.objects.create(
            media_type="movie",
            title="Delete Anonymous Test",
        )
        WatchEntry.objects.create(
            media_work=work,
        )

        response = self.client.post(
            reverse(
                "watchroom:delete_work",
                kwargs={
                    "slug": work.slug,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertTrue(
            MediaWork.objects.filter(
                pk=work.pk,
            ).exists()
        )


    def test_delete_work_is_post_only(
        self,
    ):
        work = MediaWork.objects.create(
            media_type="movie",
            title="Delete GET Test",
        )
        WatchEntry.objects.create(
            media_work=work,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            reverse(
                "watchroom:delete_work",
                kwargs={
                    "slug": work.slug,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )


    def test_owner_can_delete_work_with_history(
        self,
    ):
        work = MediaWork.objects.create(
            media_type="series",
            title="Delete Complete Test",
        )
        entry = WatchEntry.objects.create(
            media_work=work,
            status=WatchEntry.Status.WATCHING,
        )
        season = Season.objects.create(
            media_work=work,
            season_number=1,
            episode_count=10,
        )
        run = ViewingRun.objects.create(
            watch_entry=entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )
        progress = SeasonProgress.objects.create(
            viewing_run=run,
            season=season,
            episodes_watched=4,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:delete_work",
                kwargs={
                    "slug": work.slug,
                },
            )
        )

        self.assertRedirects(
            response,
            reverse("watchroom:library"),
        )
        self.assertFalse(
            MediaWork.objects.filter(
                pk=work.pk,
            ).exists()
        )
        self.assertFalse(
            WatchEntry.objects.filter(
                pk=entry.pk,
            ).exists()
        )
        self.assertFalse(
            Season.objects.filter(
                pk=season.pk,
            ).exists()
        )
        self.assertFalse(
            ViewingRun.objects.filter(
                pk=run.pk,
            ).exists()
        )
        self.assertFalse(
            SeasonProgress.objects.filter(
                pk=progress.pk,
            ).exists()
        )


class WatchroomViewingWorkflowTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects.create_user(
                username="viewing-owner",
                password="test-password",
            )
        )

        cls.movie = MediaWork.objects.create(
            media_type="movie",
            title="Saw II",
            runtime_minutes=93,
        )
        cls.movie_entry = (
            WatchEntry.objects.create(
                media_work=cls.movie,
            )
        )

        cls.series = MediaWork.objects.create(
            media_type="series",
            title="Phineas and Ferb",
            presentation="animation",
        )
        cls.series_entry = (
            WatchEntry.objects.create(
                media_work=cls.series,
            )
        )
        cls.season = Season.objects.create(
            media_work=cls.series,
            season_number=1,
            episode_count=38,
        )

    def test_owner_can_start_first_run(self):
        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:create_run",
                kwargs={
                    "slug": self.movie.slug,
                },
            ),
            {
                "new-run-progress_minutes": 20,
                "new-run-notes": "",
            },
        )

        run = ViewingRun.objects.get(
            watch_entry=self.movie_entry,
        )

        self.movie_entry.refresh_from_db()

        self.assertEqual(
            run.number,
            1,
        )
        self.assertEqual(
            run.status,
            ViewingRun.Status.WATCHING,
        )
        self.assertEqual(
            run.progress_minutes,
            20,
        )
        self.assertEqual(
            self.movie_entry.status,
            WatchEntry.Status.WATCHING,
        )

        self.assertEqual(
            run.started_on,
            timezone.localdate(),
        )

    def test_rewatch_keeps_completed_status(
        self,
    ):
        ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.COMPLETED,
        )
        self.movie_entry.status = (
            WatchEntry.Status.COMPLETED
        )
        self.movie_entry.save()

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:create_run",
                kwargs={
                    "slug": self.movie.slug,
                },
            ),
            {
                "new-run-progress_minutes": "",
                "new-run-notes": "",
            },
        )

        self.movie_entry.refresh_from_db()

        rewatch = ViewingRun.objects.get(
            watch_entry=self.movie_entry,
            number=2,
        )

        self.assertEqual(
            rewatch.status,
            ViewingRun.Status.WATCHING,
        )
        self.assertEqual(
            self.movie_entry.status,
            WatchEntry.Status.COMPLETED,
        )

    def test_pause_and_resume_sync_entry(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )
        self.movie_entry.status = (
            WatchEntry.Status.WATCHING
        )
        self.movie_entry.save()

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:transition_run",
                kwargs={
                    "slug": self.movie.slug,
                    "run_id": run.pk,
                    "action": "pause",
                },
            )
        )

        run.refresh_from_db()
        self.movie_entry.refresh_from_db()

        self.assertEqual(
            run.status,
            ViewingRun.Status.PAUSED,
        )
        self.assertEqual(
            self.movie_entry.status,
            WatchEntry.Status.PAUSED,
        )

        self.client.post(
            reverse(
                "watchroom:transition_run",
                kwargs={
                    "slug": self.movie.slug,
                    "run_id": run.pk,
                    "action": "resume",
                },
            )
        )

        run.refresh_from_db()
        self.movie_entry.refresh_from_db()

        self.assertEqual(
            run.status,
            ViewingRun.Status.WATCHING,
        )
        self.assertEqual(
            self.movie_entry.status,
            WatchEntry.Status.WATCHING,
        )

    def test_complete_movie_updates_entry(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:transition_run",
                kwargs={
                    "slug": self.movie.slug,
                    "run_id": run.pk,
                    "action": "complete",
                },
            )
        )

        run.refresh_from_db()
        self.movie_entry.refresh_from_db()

        self.assertEqual(
            run.status,
            ViewingRun.Status.COMPLETED,
        )
        self.assertIsNotNone(
            run.finished_on
        )
        self.assertEqual(
            run.progress_minutes,
            93,
        )
        self.assertEqual(
            self.movie_entry.status,
            WatchEntry.Status.COMPLETED,
        )

    def test_series_completion_requires_progress(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:transition_run",
                kwargs={
                    "slug": self.series.slug,
                    "run_id": run.pk,
                    "action": "complete",
                },
            )
        )

        run.refresh_from_db()

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertIn(
            (
                "Complete all known regular "
                "seasons"
            ),
            response.context[
                "run_action_error"
            ],
        )
        self.assertEqual(
            run.status,
            ViewingRun.Status.WATCHING,
        )

    def test_series_can_complete_with_full_progress(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )
        SeasonProgress.objects.create(
            viewing_run=run,
            season=self.season,
            episodes_watched=38,
        )

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:transition_run",
                kwargs={
                    "slug": self.series.slug,
                    "run_id": run.pk,
                    "action": "complete",
                },
            )
        )

        run.refresh_from_db()
        self.series_entry.refresh_from_db()

        self.assertEqual(
            run.status,
            ViewingRun.Status.COMPLETED,
        )
        self.assertEqual(
            self.series_entry.status,
            WatchEntry.Status.COMPLETED,
        )

    def test_dropped_rewatch_preserves_completed(
        self,
    ):
        ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.COMPLETED,
        )
        rewatch = ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=2,
            status=ViewingRun.Status.WATCHING,
        )
        self.movie_entry.status = (
            WatchEntry.Status.COMPLETED
        )
        self.movie_entry.save()

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:transition_run",
                kwargs={
                    "slug": self.movie.slug,
                    "run_id": rewatch.pk,
                    "action": "drop",
                },
            )
        )

        rewatch.refresh_from_db()
        self.movie_entry.refresh_from_db()

        self.assertEqual(
            rewatch.status,
            ViewingRun.Status.DROPPED,
        )
        self.assertEqual(
            self.movie_entry.status,
            WatchEntry.Status.COMPLETED,
        )

    def test_owner_can_update_movie_minutes(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.PAUSED,
        )

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:update_run",
                kwargs={
                    "slug": self.movie.slug,
                    "run_id": run.pk,
                },
            ),
            {
                f"run-{run.pk}-started_on": "",
                f"run-{run.pk}-finished_on": "",
                f"run-{run.pk}-progress_minutes": 45,
                f"run-{run.pk}-notes": (
                    "Paused halfway."
                ),
            },
        )

        run.refresh_from_db()

        self.assertEqual(
            run.progress_minutes,
            45,
        )
        self.assertEqual(
            run.notes,
            "Paused halfway.",
        )

    def test_owner_can_upsert_season_progress(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:update_season_progress",
                kwargs={
                    "slug": self.series.slug,
                    "run_id": run.pk,
                    "season_id": self.season.pk,
                },
            ),
            {
                (
                    f"progress-{run.pk}-"
                    f"{self.season.pk}-"
                    "episodes_watched"
                ): 12,
                (
                    f"progress-{run.pk}-"
                    f"{self.season.pk}-"
                    "started_on"
                ): "",
                (
                    f"progress-{run.pk}-"
                    f"{self.season.pk}-"
                    "finished_on"
                ): "",
            },
        )

        progress = SeasonProgress.objects.get(
            viewing_run=run,
            season=self.season,
        )

        self.assertEqual(
            progress.episodes_watched,
            12,
        )

    def test_progress_update_is_post_only(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            reverse(
                "watchroom:update_season_progress",
                kwargs={
                    "slug": self.series.slug,
                    "run_id": run.pk,
                    "season_id": self.season.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    def test_cross_work_season_returns_404(
        self,
    ):
        other_series = MediaWork.objects.create(
            media_type="series",
            title="Other Series",
        )
        other_season = Season.objects.create(
            media_work=other_series,
            season_number=1,
            episode_count=10,
        )
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:update_season_progress",
                kwargs={
                    "slug": self.series.slug,
                    "run_id": run.pk,
                    "season_id": other_season.pk,
                },
            ),
            {},
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_anonymous_transition_redirects(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        response = self.client.post(
            reverse(
                "watchroom:transition_run",
                kwargs={
                    "slug": self.movie.slug,
                    "run_id": run.pk,
                    "action": "pause",
                },
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertIn(
            reverse("login"),
            response.url,
        )

    def test_series_detail_uses_one_viewing_panel(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.series_entry,
            number=1,
            status=ViewingRun.Status.WATCHING,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            self.series.get_absolute_url()
        )

        self.assertContains(
            response,
            'id="viewing-controls"',
            count=1,
        )
        self.assertContains(
            response,
            'id="season-progress"',
            count=1,
        )
        self.assertNotContains(
            response,
            "Optional dates",
        )

    def test_owner_can_clear_run_dates(
        self,
    ):
        run = ViewingRun.objects.create(
            watch_entry=self.movie_entry,
            number=1,
            status=ViewingRun.Status.COMPLETED,
            started_on=date(
                2026,
                7,
                1,
            ),
            finished_on=date(
                2026,
                7,
                2,
            ),
            progress_minutes=93,
        )

        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:update_run",
                kwargs={
                    "slug": self.movie.slug,
                    "run_id": run.pk,
                },
            ),
            {
                f"run-{run.pk}-started_on": "",
                f"run-{run.pk}-finished_on": "",
                (
                    f"run-{run.pk}-"
                    "progress_minutes"
                ): 93,
                f"run-{run.pk}-notes": "",
            },
        )

        run.refresh_from_db()

        self.assertIsNone(
            run.started_on
        )
        self.assertIsNone(
            run.finished_on
        )


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

    @patch(
        "watchroom.services."
        "tmdb_client.requests.get"
    )
    def test_collection_details_endpoint(
        self,
        mock_get,
    ):
        mock_get.return_value = (
            build_mock_response(
                payload={
                    "id": 656,
                    "name": "Saw Collection",
                    "parts": [],
                },
            )
        )

        client = TMDBClient(
            access_token="tmdb-token"
        )

        result = client.get_collection(
            656
        )

        self.assertEqual(
            result["id"],
            656,
        )

        args, _kwargs = mock_get.call_args

        self.assertEqual(
            args[0],
            (
                "https://api."
                "themoviedb.org/3/"
                "collection/656"
            ),
        )


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

    def test_collection_parts_use_release_order(
        self,
    ):
        result = normalize_collection_details(
            {
                "id": 656,
                "name": "Saw Collection",
                "parts": [
                    {
                        "id": 215,
                        "title": "Saw II",
                        "release_date": (
                            "2005-10-28"
                        ),
                    },
                    {
                        "id": 176,
                        "title": "Saw",
                        "release_date": (
                            "2004-10-01"
                        ),
                    },
                ],
            }
        )

        self.assertEqual(
            result["tmdb_collection_id"],
            656,
        )
        self.assertEqual(
            [
                part["tmdb_id"]
                for part in result["parts"]
            ],
            [
                176,
                215,
            ],
        )


class TMDBSearchViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects.create_user(
                username="tmdb-owner",
                password="test-password",
            )
        )

    def setUp(self):
        self.client.force_login(
            self.owner
        )

    def test_search_requires_login(self):
        self.client.logout()

        response = self.client.get(
            reverse(
                "watchroom:tmdb_search"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertIn(
            reverse("login"),
            response.url,
        )

    @patch(
        "watchroom.web.tmdb.TMDBClient"
    )
    def test_unbound_page_does_not_call_tmdb(
        self,
        mock_client,
    ):
        response = self.client.get(
            reverse(
                "watchroom:tmdb_search"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "watchroom/tmdb_search.html",
        )
        mock_client.assert_not_called()

    @patch(
        "watchroom.web.tmdb.TMDBClient"
    )
    def test_owner_can_search_movies(
        self,
        mock_client,
    ):
        mock_client.return_value.search_movie.return_value = [
            {
                "id": 11,
                "title": "Saw",
                "original_title": "Saw",
                "overview": "A horror movie.",
                "release_date": "2004-10-29",
                "genre_ids": [27],
            },
        ]

        response = self.client.get(
            reverse(
                "watchroom:tmdb_search"
            ),
            {
                "media_type": "movie",
                "query": "Saw",
            },
        )

        mock_client.return_value.search_movie.assert_called_once_with(
            "Saw",
            limit=12,
        )
        mock_client.return_value.search_series.assert_not_called()

        self.assertContains(
            response,
            "Saw",
        )
        self.assertContains(
            response,
            "Review &amp; Import",
        )
        self.assertContains(
            response,
            reverse(
                "watchroom:tmdb_import",
                args=[
                    "movie",
                    11,
                ],
            ),
        )
        self.assertContains(
            response,
            "Review",
        )
        self.assertContains(
            response,
            "Import",
        )

    @patch(
        "watchroom.web.tmdb.TMDBClient"
    )
    def test_owner_can_search_series(
        self,
        mock_client,
    ):
        mock_client.return_value.search_series.return_value = [
            {
                "id": 22,
                "name": "Phineas and Ferb",
                "original_name": (
                    "Phineas and Ferb"
                ),
                "overview": "Summer adventures.",
                "first_air_date": "2007-08-17",
                "genre_ids": [16],
                "origin_country": ["US"],
            },
        ]

        response = self.client.get(
            reverse(
                "watchroom:tmdb_search"
            ),
            {
                "media_type": "series",
                "query": "Phineas and Ferb",
            },
        )

        mock_client.return_value.search_series.assert_called_once_with(
            "Phineas and Ferb",
            limit=12,
        )
        mock_client.return_value.search_movie.assert_not_called()

        self.assertContains(
            response,
            "Phineas and Ferb",
        )
        self.assertContains(
            response,
            "Animation / Cartoon",
        )

    @patch(
        "watchroom.web.tmdb.TMDBClient"
    )
    def test_search_marks_existing_work(
        self,
        mock_client,
    ):
        work = MediaWork.objects.create(
            tmdb_id=33,
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="Existing Movie",
        )

        mock_client.return_value.search_movie.return_value = [
            {
                "id": 33,
                "title": "Existing Movie",
                "original_title": (
                    "Existing Movie"
                ),
                "genre_ids": [18],
            },
        ]

        response = self.client.get(
            reverse(
                "watchroom:tmdb_search"
            ),
            {
                "media_type": "movie",
                "query": "Existing Movie",
            },
        )

        self.assertContains(
            response,
            "Already Imported",
        )
        self.assertContains(
            response,
            work.get_absolute_url(),
        )

    @patch(
        "watchroom.web.tmdb.TMDBClient"
    )
    def test_client_error_is_displayed(
        self,
        mock_client,
    ):
        mock_client.return_value.search_movie.side_effect = (
            TMDBRequestError(
                "TMDB is unavailable."
            )
        )

        response = self.client.get(
            reverse(
                "watchroom:tmdb_search"
            ),
            {
                "media_type": "movie",
                "query": "Saw",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "TMDB Search Failed",
        )
        self.assertContains(
            response,
            "TMDB is unavailable.",
        )

    @patch(
        "watchroom.web.tmdb.TMDBClient"
    )
    def test_invalid_result_is_skipped(
        self,
        mock_client,
    ):
        mock_client.return_value.search_series.return_value = [
            {
                "name": "Missing ID",
            },
            {
                "id": 44,
                "name": "Valid Series",
                "original_name": (
                    "Valid Series"
                ),
            },
        ]

        response = self.client.get(
            reverse(
                "watchroom:tmdb_search"
            ),
            {
                "media_type": "series",
                "query": "Series",
            },
        )

        self.assertEqual(
            len(
                response.context[
                    "results"
                ]
            ),
            1,
        )
        self.assertContains(
            response,
            "Valid Series",
        )


class TMDBImportFormTests(
    SimpleTestCase
):
    def test_import_statuses_exclude_active_states(
        self,
    ):
        form = TMDBImportForm()

        status_values = {
            value
            for value, _label
            in form.fields[
                "status"
            ].choices
        }

        self.assertIn(
            WatchEntry.Status.PLAN_TO_WATCH,
            status_values,
        )
        self.assertIn(
            WatchEntry.Status.COMPLETED,
            status_values,
        )
        self.assertIn(
            WatchEntry.Status.DROPPED,
            status_values,
        )
        self.assertNotIn(
            WatchEntry.Status.WATCHING,
            status_values,
        )
        self.assertNotIn(
            WatchEntry.Status.PAUSED,
            status_values,
        )


class TMDBImporterTests(TestCase):
    def movie_details(self):
        return {
            "tmdb_id": 11,
            "media_type": (
                MediaWork.MediaType.MOVIE
            ),
            "title": "Saw",
            "original_title": "Saw",
            "overview": "A horror movie.",
            "presentation": (
                MediaWork.Presentation
                .LIVE_ACTION
            ),
            "original_language": "en",
            "first_release_date": date(
                2004,
                10,
                29,
            ),
            "runtime_minutes": 103,
            "external_status": "Released",
            "poster_url": (
                "https://example.com/poster.jpg"
            ),
            "backdrop_url": (
                "https://example.com/backdrop.jpg"
            ),
            "genres": [
                "Horror",
            ],
            "origin_countries": [
                "US",
            ],
            "networks": [],
            "tmdb_payload": {
                "id": 11,
            },
        }

    def series_details(self):
        return {
            "tmdb_id": 22,
            "media_type": (
                MediaWork.MediaType.SERIES
            ),
            "title": "Phineas and Ferb",
            "original_title": (
                "Phineas and Ferb"
            ),
            "overview": "Summer adventures.",
            "presentation": (
                MediaWork.Presentation
                .ANIMATION
            ),
            "original_language": "en",
            "first_release_date": date(
                2007,
                8,
                17,
            ),
            "runtime_minutes": None,
            "external_status": "Ended",
            "poster_url": "",
            "backdrop_url": "",
            "genres": [
                "Animation",
                "Comedy",
            ],
            "origin_countries": [
                "US",
            ],
            "networks": [
                "Disney Channel",
            ],
            "tmdb_payload": {
                "id": 22,
            },
            "seasons": [
                {
                    "tmdb_id": 220,
                    "season_number": 0,
                    "name": "Specials",
                    "episode_count": 4,
                    "air_date": None,
                    "poster_url": "",
                    "tmdb_payload": {
                        "id": 220,
                    },
                },
                {
                    "tmdb_id": 221,
                    "season_number": 1,
                    "name": "Season 1",
                    "episode_count": 38,
                    "air_date": None,
                    "poster_url": "",
                    "tmdb_payload": {
                        "id": 221,
                    },
                },
            ],
        }

    def test_movie_import_creates_local_records(
        self,
    ):
        work = import_tmdb_work(
            details=self.movie_details(),
            status=(
                WatchEntry.Status
                .PLAN_TO_WATCH
            ),
            notes="Watch later.",
            presentation=(
                MediaWork.Presentation
                .LIVE_ACTION
            ),
        )

        entry = work.watch_entry

        self.assertEqual(
            work.tmdb_id,
            11,
        )
        self.assertEqual(
            work.runtime_minutes,
            103,
        )
        self.assertEqual(
            work.genres,
            [
                "Horror",
            ],
        )
        self.assertIsNotNone(
            work.tmdb_synced_at
        )
        self.assertEqual(
            entry.status,
            WatchEntry.Status.PLAN_TO_WATCH,
        )
        self.assertEqual(
            entry.notes,
            "Watch later.",
        )

    def test_series_import_creates_seasons(
        self,
    ):
        work = import_tmdb_work(
            details=self.series_details(),
            status=(
                WatchEntry.Status
                .PLAN_TO_WATCH
            ),
            presentation=(
                MediaWork.Presentation
                .ANIMATION
            ),
        )

        self.assertEqual(
            work.seasons.count(),
            2,
        )
        self.assertTrue(
            work.seasons.filter(
                season_number=0,
                episode_count=4,
            ).exists()
        )
        self.assertTrue(
            work.seasons.filter(
                season_number=1,
                episode_count=38,
            ).exists()
        )

    def test_completed_series_gets_full_progress(
        self,
    ):
        work = import_tmdb_work(
            details=self.series_details(),
            status=(
                WatchEntry.Status.COMPLETED
            ),
            presentation=(
                MediaWork.Presentation
                .ANIMATION
            ),
        )

        run = work.watch_entry.viewing_runs.get(
            number=1
        )

        season_one = work.seasons.get(
            season_number=1
        )

        progress = SeasonProgress.objects.get(
            viewing_run=run,
            season=season_one,
        )

        self.assertEqual(
            run.status,
            ViewingRun.Status.COMPLETED,
        )
        self.assertEqual(
            progress.episodes_watched,
            38,
        )
        self.assertFalse(
            SeasonProgress.objects.filter(
                viewing_run=run,
                season__season_number=0,
            ).exists()
        )

    def test_duplicate_import_is_rejected(
        self,
    ):
        existing = MediaWork.objects.create(
            tmdb_id=11,
            media_type=(
                MediaWork.MediaType.MOVIE
            ),
            title="Saw",
        )

        with self.assertRaises(
            TMDBDuplicateWorkError
        ) as context:
            import_tmdb_work(
                details=self.movie_details(),
                status=(
                    WatchEntry.Status
                    .PLAN_TO_WATCH
                ),
                presentation=(
                    MediaWork.Presentation
                    .LIVE_ACTION
                ),
            )

        self.assertEqual(
            context.exception.existing_work,
            existing,
        )

    def saw_collection(
        self,
    ):
        return {
            "tmdb_collection_id": 656,
            "name": "Saw Collection",
            "overview": "Saw movies.",
            "poster_url": "",
            "backdrop_url": "",
            "tmdb_payload": {
                "id": 656,
            },
            "parts": [
                {
                    "tmdb_id": 176,
                    "title": "Saw",
                    "first_release_date": (
                        date(2004, 10, 1)
                    ),
                },
                {
                    "tmdb_id": 215,
                    "title": "Saw II",
                    "first_release_date": (
                        date(2005, 10, 28)
                    ),
                },
            ],
        }


    def test_movie_import_creates_tmdb_franchise(
        self,
    ):
        details = self.movie_details()
        details["tmdb_id"] = 176
        details["collection"] = (
            self.saw_collection()
        )

        work = import_tmdb_work(
            details=details,
            status=(
                WatchEntry.Status
                .PLAN_TO_WATCH
            ),
            presentation="live_action",
        )

        franchise = Franchise.objects.get(
            tmdb_collection_id=656
        )
        membership = (
            FranchiseMembership.objects.get(
                franchise=franchise,
                media_work=work,
            )
        )

        self.assertEqual(
            franchise.name,
            "Saw Collection",
        )
        self.assertEqual(
            membership.position,
            1,
        )
        self.assertEqual(
            membership.role,
            FranchiseMembership.Role.MAIN,
        )


    def test_second_movie_reuses_tmdb_franchise(
        self,
    ):
        first = self.movie_details()
        first["tmdb_id"] = 176
        first["title"] = "Saw"
        first["collection"] = (
            self.saw_collection()
        )

        second = self.movie_details()
        second["tmdb_id"] = 215
        second["title"] = "Saw II"
        second["collection"] = (
            self.saw_collection()
        )

        first_work = import_tmdb_work(
            details=first,
            status="plan_to_watch",
            presentation="live_action",
        )
        second_work = import_tmdb_work(
            details=second,
            status="plan_to_watch",
            presentation="live_action",
        )

        franchise = Franchise.objects.get(
            tmdb_collection_id=656
        )

        self.assertEqual(
            Franchise.objects.filter(
                tmdb_collection_id=656
            ).count(),
            1,
        )
        self.assertEqual(
            franchise.memberships.get(
                media_work=first_work
            ).position,
            1,
        )
        self.assertEqual(
            franchise.memberships.get(
                media_work=second_work
            ).position,
            2,
        )


class TMDBImportViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects.create_user(
                username="tmdb-import-owner",
                password="test-password",
            )
        )

    def setUp(self):
        self.client.force_login(
            self.owner
        )

    def series_details(self):
        return {
            "tmdb_id": 22,
            "media_type": (
                MediaWork.MediaType.SERIES
            ),
            "title": "Phineas and Ferb",
            "original_title": (
                "Phineas and Ferb"
            ),
            "overview": "Summer adventures.",
            "presentation": (
                MediaWork.Presentation
                .ANIMATION
            ),
            "original_language": "en",
            "first_release_date": date(
                2007,
                8,
                17,
            ),
            "runtime_minutes": None,
            "external_status": "Ended",
            "poster_url": "",
            "backdrop_url": "",
            "genres": [
                "Animation",
            ],
            "origin_countries": [
                "US",
            ],
            "networks": [
                "Disney Channel",
            ],
            "tmdb_payload": {
                "id": 22,
            },
            "seasons": [
                {
                    "tmdb_id": 221,
                    "season_number": 1,
                    "name": "Season 1",
                    "episode_count": 38,
                    "air_date": None,
                    "poster_url": "",
                    "tmdb_payload": {
                        "id": 221,
                    },
                },
            ],
        }

    def test_import_review_requires_login(
        self,
    ):
        self.client.logout()

        response = self.client.get(
            reverse(
                "watchroom:tmdb_import",
                args=[
                    "series",
                    22,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertIn(
            reverse("login"),
            response.url,
        )

    @patch(
        "watchroom.web.tmdb."
        "fetch_tmdb_details"
    )
    def test_import_review_shows_details(
        self,
        mock_fetch,
    ):
        mock_fetch.return_value = (
            self.series_details()
        )

        response = self.client.get(
            reverse(
                "watchroom:tmdb_import",
                args=[
                    "series",
                    22,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "watchroom/tmdb_import.html",
        )
        self.assertContains(
            response,
            "Phineas and Ferb",
        )
        self.assertContains(
            response,
            "38",
        )
        self.assertContains(
            response,
            "Import to Watchroom",
        )

    @patch(
        "watchroom.web.tmdb."
        "fetch_tmdb_details"
    )
    def test_owner_can_import_series(
        self,
        mock_fetch,
    ):
        mock_fetch.return_value = (
            self.series_details()
        )

        response = self.client.post(
            reverse(
                "watchroom:tmdb_import",
                args=[
                    "series",
                    22,
                ],
            ),
            {
                "presentation": "animation",
                "status": "plan_to_watch",
                "notes": "Summer project.",
            },
        )

        work = MediaWork.objects.get(
            media_type="series",
            tmdb_id=22,
        )

        self.assertRedirects(
            response,
            work.get_absolute_url(),
        )
        self.assertEqual(
            work.watch_entry.notes,
            "Summer project.",
        )
        self.assertEqual(
            work.seasons.count(),
            1,
        )

    @patch(
        "watchroom.web.tmdb."
        "fetch_tmdb_details"
    )
    def test_existing_import_redirects_without_fetch(
        self,
        mock_fetch,
    ):
        work = MediaWork.objects.create(
            media_type="series",
            tmdb_id=22,
            title="Phineas and Ferb",
        )
        WatchEntry.objects.create(
            media_work=work,
            status=(
                WatchEntry.Status.PLAN_TO_WATCH
            ),
        )

        response = self.client.get(
            reverse(
                "watchroom:tmdb_import",
                args=[
                    "series",
                    22,
                ],
            )
        )

        self.assertRedirects(
            response,
            work.get_absolute_url(),
        )
        mock_fetch.assert_not_called()

    @patch(
        "watchroom.web.tmdb."
        "fetch_tmdb_details"
    )
    def test_tmdb_error_is_displayed(
        self,
        mock_fetch,
    ):
        mock_fetch.side_effect = (
            TMDBImportError(
                "TMDB details unavailable."
            )
        )

        response = self.client.get(
            reverse(
                "watchroom:tmdb_import",
                args=[
                    "series",
                    22,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "TMDB Import Failed",
        )
        self.assertContains(
            response,
            "TMDB details unavailable.",
        )


class TMDBRefreshServiceTests(
    TestCase
):
    def create_movie(self):
        work = MediaWork.objects.create(
            media_type="movie",
            tmdb_id=176,
            title="Saw",
            runtime_minutes=103,
        )
        entry = WatchEntry.objects.create(
            media_work=work,
            status=(
                WatchEntry.Status.COMPLETED
            ),
        )
        run = ViewingRun.objects.create(
            watch_entry=entry,
            number=1,
            status=(
                ViewingRun.Status.COMPLETED
            ),
            progress_minutes=103,
        )

        return work, entry, run

    def create_series(self):
        work = MediaWork.objects.create(
            media_type="series",
            tmdb_id=1877,
            title="Phineas and Ferb",
            presentation="animation",
        )
        entry = WatchEntry.objects.create(
            media_work=work,
            status=(
                WatchEntry.Status.WATCHING
            ),
        )
        season = Season.objects.create(
            media_work=work,
            tmdb_id=1001,
            season_number=1,
            name="Season 1",
            episode_count=47,
        )
        run = ViewingRun.objects.create(
            watch_entry=entry,
            number=1,
            status=(
                ViewingRun.Status.WATCHING
            ),
        )

        return (
            work,
            entry,
            season,
            run,
        )

    @patch(
        "watchroom.services."
        "tmdb_refresh.fetch_tmdb_details"
    )
    def test_movie_refresh_preserves_history(
        self,
        mock_fetch,
    ):
        work, entry, run = (
            self.create_movie()
        )

        mock_fetch.return_value = {
            "tmdb_id": 176,
            "media_type": "movie",
            "title": "Saw",
            "overview": "Updated overview.",
            "runtime_minutes": 110,
            "external_status": "Released",
            "genres": [
                "Horror",
                "Mystery",
            ],
            "tmdb_payload": {
                "id": 176,
            },
        }

        refresh_work_from_tmdb(
            work=work
        )

        work.refresh_from_db()
        entry.refresh_from_db()
        run.refresh_from_db()

        self.assertEqual(
            work.overview,
            "Updated overview.",
        )
        self.assertEqual(
            work.runtime_minutes,
            110,
        )
        self.assertEqual(
            entry.status,
            WatchEntry.Status.COMPLETED,
        )
        self.assertEqual(
            run.progress_minutes,
            103,
        )
        self.assertEqual(
            run.status,
            ViewingRun.Status.COMPLETED,
        )

    @patch(
        "watchroom.services."
        "tmdb_refresh.fetch_tmdb_details"
    )
    def test_movie_runtime_cannot_drop_below_progress(
        self,
        mock_fetch,
    ):
        work, _entry, _run = (
            self.create_movie()
        )

        mock_fetch.return_value = {
            "tmdb_id": 176,
            "media_type": "movie",
            "title": "Saw",
            "runtime_minutes": 90,
            "tmdb_payload": {
                "id": 176,
            },
        }

        result = refresh_work_from_tmdb(
            work=work
        )

        work.refresh_from_db()

        self.assertEqual(
            work.runtime_minutes,
            103,
        )
        self.assertTrue(
            result.preserved_runtime
        )

    @patch(
        "watchroom.services."
        "tmdb_refresh.fetch_tmdb_details"
    )
    def test_series_refresh_updates_and_creates_seasons(
        self,
        mock_fetch,
    ):
        (
            work,
            entry,
            season,
            run,
        ) = self.create_series()

        mock_fetch.return_value = {
            "tmdb_id": 1877,
            "media_type": "series",
            "title": "Phineas and Ferb",
            "external_status": (
                "Returning Series"
            ),
            "tmdb_payload": {
                "id": 1877,
            },
            "seasons": [
                {
                    "tmdb_id": 1001,
                    "season_number": 1,
                    "name": "Season 1",
                    "episode_count": 48,
                    "tmdb_payload": {
                        "id": 1001,
                    },
                },
                {
                    "tmdb_id": 1002,
                    "season_number": 2,
                    "name": "Season 2",
                    "episode_count": 66,
                    "tmdb_payload": {
                        "id": 1002,
                    },
                },
            ],
        }

        result = refresh_work_from_tmdb(
            work=work
        )

        season.refresh_from_db()
        entry.refresh_from_db()
        run.refresh_from_db()

        self.assertEqual(
            season.episode_count,
            48,
        )
        self.assertTrue(
            work.seasons.filter(
                season_number=2,
                episode_count=66,
            ).exists()
        )
        self.assertEqual(
            result.created_seasons,
            1,
        )
        self.assertEqual(
            result.updated_seasons,
            1,
        )
        self.assertEqual(
            entry.status,
            WatchEntry.Status.WATCHING,
        )
        self.assertEqual(
            run.status,
            ViewingRun.Status.WATCHING,
        )

    @patch(
        "watchroom.services."
        "tmdb_refresh.fetch_tmdb_details"
    )
    def test_season_total_cannot_drop_below_progress(
        self,
        mock_fetch,
    ):
        (
            work,
            _entry,
            season,
            run,
        ) = self.create_series()

        SeasonProgress.objects.create(
            viewing_run=run,
            season=season,
            episodes_watched=47,
        )

        mock_fetch.return_value = {
            "tmdb_id": 1877,
            "media_type": "series",
            "title": "Phineas and Ferb",
            "tmdb_payload": {
                "id": 1877,
            },
            "seasons": [
                {
                    "tmdb_id": 1001,
                    "season_number": 1,
                    "name": "Season 1",
                    "episode_count": 40,
                    "tmdb_payload": {
                        "id": 1001,
                    },
                },
            ],
        }

        result = refresh_work_from_tmdb(
            work=work
        )

        season.refresh_from_db()

        self.assertEqual(
            season.episode_count,
            47,
        )
        self.assertEqual(
            (
                result
                .preserved_episode_totals
            ),
            1,
        )

    @patch(
        "watchroom.services."
        "tmdb_refresh.fetch_tmdb_details"
    )
    def test_missing_tmdb_season_is_not_deleted(
        self,
        mock_fetch,
    ):
        (
            work,
            _entry,
            season,
            _run,
        ) = self.create_series()

        mock_fetch.return_value = {
            "tmdb_id": 1877,
            "media_type": "series",
            "title": "Phineas and Ferb",
            "tmdb_payload": {
                "id": 1877,
            },
            "seasons": [],
        }

        refresh_work_from_tmdb(
            work=work
        )

        self.assertTrue(
            Season.objects.filter(
                pk=season.pk,
            ).exists()
        )

    @patch(
        "watchroom.services."
        "tmdb_refresh.fetch_tmdb_details"
    )
    def test_movie_refresh_links_collection(
        self,
        mock_fetch,
    ):
        work, _entry, _run = (
            self.create_movie()
        )

        mock_fetch.return_value = {
            "tmdb_id": 176,
            "media_type": "movie",
            "title": "Saw",
            "runtime_minutes": 103,
            "tmdb_payload": {
                "id": 176,
            },
            "collection": {
                "tmdb_collection_id": 656,
                "name": "Saw Collection",
                "overview": "",
                "poster_url": "",
                "backdrop_url": "",
                "tmdb_payload": {
                    "id": 656,
                },
                "parts": [
                    {
                        "tmdb_id": 176,
                    },
                ],
            },
        }

        result = refresh_work_from_tmdb(
            work=work
        )

        self.assertTrue(
            result.franchise_created
        )
        self.assertTrue(
            result.franchise_linked
        )
        self.assertTrue(
            work.franchises.filter(
                tmdb_collection_id=656
            ).exists()
        )


class TMDBRefreshViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects.create_user(
                username="tmdb-refresh-owner",
                password="test-password",
            )
        )

        cls.work = MediaWork.objects.create(
            media_type="series",
            tmdb_id=1877,
            title="Phineas and Ferb",
            presentation="animation",
        )
        cls.entry = WatchEntry.objects.create(
            media_work=cls.work,
            status=(
                WatchEntry.Status
                .PLAN_TO_WATCH
            ),
        )

    def test_refresh_requires_login(
        self,
    ):
        response = self.client.post(
            reverse(
                "watchroom:refresh_tmdb",
                kwargs={
                    "slug": self.work.slug,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertIn(
            reverse("login"),
            response.url,
        )

    def test_refresh_is_post_only(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        response = self.client.get(
            reverse(
                "watchroom:refresh_tmdb",
                kwargs={
                    "slug": self.work.slug,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    @patch(
        "watchroom.web.tmdb."
        "refresh_work_from_tmdb"
    )
    def test_owner_can_refresh_tmdb_work(
        self,
        mock_refresh,
    ):
        mock_refresh.return_value = (
            TMDBRefreshResult(
                work=self.work,
                created_seasons=1,
                updated_seasons=4,
            )
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:refresh_tmdb",
                kwargs={
                    "slug": self.work.slug,
                },
            ),
            follow=True,
        )

        mock_refresh.assert_called_once()

        refreshed_work = (
            mock_refresh.call_args
            .kwargs["work"]
        )

        self.assertEqual(
            refreshed_work,
            self.work,
        )
        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "TMDB refresh complete.",
        )
        self.assertContains(
            response,
            (
                "1 season(s) added and "
                "4 season(s) updated."
            ),
        )

    @patch(
        "watchroom.web.tmdb."
        "refresh_work_from_tmdb"
    )
    def test_refresh_error_is_displayed(
        self,
        mock_refresh,
    ):
        mock_refresh.side_effect = (
            TMDBRefreshError(
                "TMDB is unavailable."
            )
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:refresh_tmdb",
                kwargs={
                    "slug": self.work.slug,
                },
            ),
            follow=True,
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            (
                "TMDB refresh failed: "
                "TMDB is unavailable."
            ),
        )

    @patch(
        "watchroom.web.tmdb."
        "refresh_work_from_tmdb"
    )
    def test_unlinked_work_cannot_refresh(
        self,
        mock_refresh,
    ):
        work = MediaWork.objects.create(
            media_type="movie",
            title="Manual Movie",
        )
        WatchEntry.objects.create(
            media_work=work,
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:refresh_tmdb",
                kwargs={
                    "slug": work.slug,
                },
            ),
            follow=True,
        )

        mock_refresh.assert_not_called()

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            (
                "This work is not linked "
                "to TMDB."
            ),
        )


class WatchroomFranchiseViewTests(
    TestCase
):
    @classmethod
    def setUpTestData(cls):
        cls.owner = (
            get_user_model()
            .objects.create_user(
                username="franchise-owner",
                password="test-password",
            )
        )

        cls.series = MediaWork.objects.create(
            media_type="series",
            title="Phineas and Ferb",
            presentation="animation",
        )
        WatchEntry.objects.create(
            media_work=cls.series,
        )

        cls.movie = MediaWork.objects.create(
            media_type="movie",
            title="Across the 2nd Dimension",
            presentation="animation",
            runtime_minutes=78,
        )
        WatchEntry.objects.create(
            media_work=cls.movie,
        )

        cls.franchise = (
            Franchise.objects.create(
                name="Phineas and Ferb",
            )
        )
        cls.membership = (
            FranchiseMembership.objects.create(
                franchise=cls.franchise,
                media_work=cls.series,
                position=1,
                role=(
                    FranchiseMembership
                    .Role.MAIN
                ),
            )
        )

    def test_franchise_index_is_public(
        self,
    ):
        response = self.client.get(
            reverse(
                "watchroom:franchise_index"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            "Phineas and Ferb",
        )

    def test_franchise_detail_is_public(
        self,
    ):
        response = self.client.get(
            self.franchise.get_absolute_url()
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertContains(
            response,
            self.series.title,
        )
        self.assertNotContains(
            response,
            "Franchise Management",
        )

    def test_owner_can_create_franchise(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:create_franchise"
            ),
            {
                "franchise-name": "Saw",
                "franchise-overview": "",
                "franchise-backdrop_url": "",
            },
        )

        franchise = Franchise.objects.get(
            name="Saw"
        )

        self.assertRedirects(
            response,
            franchise.get_absolute_url(),
        )

    def test_owner_can_add_member(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:add_franchise_member",
                kwargs={
                    "slug": (
                        self.franchise.slug
                    ),
                },
            ),
            {
                "new-member-media_work": (
                    self.movie.pk
                ),
                "new-member-position": 2,
                "new-member-role": "main",
                "new-member-notes": "",
            },
        )

        self.assertTrue(
            FranchiseMembership.objects.filter(
                franchise=self.franchise,
                media_work=self.movie,
                position=2,
            ).exists()
        )

    def test_owner_can_update_membership(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:update_franchise_member",
                kwargs={
                    "slug": (
                        self.franchise.slug
                    ),
                    "membership_id": (
                        self.membership.pk
                    ),
                },
            ),
            {
                (
                    f"member-"
                    f"{self.membership.pk}-"
                    "media_work"
                ): self.series.pk,
                (
                    f"member-"
                    f"{self.membership.pk}-"
                    "position"
                ): 3,
                (
                    f"member-"
                    f"{self.membership.pk}-"
                    "role"
                ): "special",
                (
                    f"member-"
                    f"{self.membership.pk}-"
                    "notes"
                ): "Updated.",
            },
        )

        self.membership.refresh_from_db()

        self.assertEqual(
            self.membership.position,
            3,
        )
        self.assertEqual(
            self.membership.role,
            "special",
        )

    def test_removing_membership_preserves_work(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        self.client.post(
            reverse(
                "watchroom:remove_franchise_member",
                kwargs={
                    "slug": (
                        self.franchise.slug
                    ),
                    "membership_id": (
                        self.membership.pk
                    ),
                },
            )
        )

        self.assertFalse(
            FranchiseMembership.objects.filter(
                pk=self.membership.pk,
            ).exists()
        )
        self.assertTrue(
            MediaWork.objects.filter(
                pk=self.series.pk,
            ).exists()
        )

    def test_nonempty_franchise_cannot_be_deleted(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:delete_franchise",
                kwargs={
                    "slug": (
                        self.franchise.slug
                    ),
                },
            ),
            follow=True,
        )

        self.assertTrue(
            Franchise.objects.filter(
                pk=self.franchise.pk,
            ).exists()
        )
        self.assertContains(
            response,
            "Remove every work",
        )

    def test_owner_can_delete_empty_franchise(
        self,
    ):
        franchise = Franchise.objects.create(
            name="Empty Franchise",
        )

        self.client.force_login(
            self.owner
        )

        response = self.client.post(
            reverse(
                "watchroom:delete_franchise",
                kwargs={
                    "slug": franchise.slug,
                },
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "watchroom:franchise_index"
            ),
        )
        self.assertFalse(
            Franchise.objects.filter(
                pk=franchise.pk,
            ).exists()
        )

    def test_work_detail_links_to_franchise(
        self,
    ):
        response = self.client.get(
            self.series.get_absolute_url()
        )

        self.assertContains(
            response,
            self.franchise.get_absolute_url(),
        )
        self.assertContains(
            response,
            "Position",
        )

    def test_franchise_form_exposes_background_image(
        self,
    ):
        form = FranchiseOwnerForm(
            instance=self.franchise,
        )

        self.assertIn(
            "backdrop_url",
            form.fields,
        )
        self.assertNotIn(
            "poster_url",
            form.fields,
        )
        self.assertEqual(
            form.fields[
                "backdrop_url"
            ].label,
            "Background Image URL",
        )


    def test_franchise_form_exposes_background_image(
        self,
    ):
        form = FranchiseOwnerForm(
            instance=self.franchise,
        )

        self.assertIn(
            "backdrop_url",
            form.fields,
        )
        self.assertNotIn(
            "poster_url",
            form.fields,
        )
        self.assertEqual(
            form.fields[
                "backdrop_url"
            ].label,
            "Background Image URL",
        )

    def test_owner_can_update_franchise_background(
        self,
    ):
        self.client.force_login(
            self.owner
        )

        image_url = (
            "https://example.com/"
            "phineas-background.jpg"
        )

        self.client.post(
            reverse(
                "watchroom:update_franchise",
                kwargs={
                    "slug": self.franchise.slug,
                },
            ),
            {
                "franchise-name": (
                    self.franchise.name
                ),
                "franchise-overview": "",
                "franchise-backdrop_url": (
                    image_url
                ),
            },
        )

        self.franchise.refresh_from_db()

        self.assertEqual(
            self.franchise.backdrop_url,
            image_url,
        )