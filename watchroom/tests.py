from datetime import date

from django.urls import reverse
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

from django.test import TestCase

from .models import (
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
)


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

    def test_finish_date_requires_complete_season(
        self,
    ):
        progress = SeasonProgress(
            viewing_run=self.series_run,
            season=self.season,
            episodes_watched=12,
            finished_on=date(
                2026,
                7,
                24,
            ),
        )

        with self.assertRaises(
            ValidationError
        ):
            progress.full_clean()

    def test_complete_season_accepts_finish_date(
        self,
    ):
        progress = SeasonProgress(
            viewing_run=self.series_run,
            season=self.season,
            episodes_watched=38,
            started_on=date(
                2026,
                7,
                1,
            ),
            finished_on=date(
                2026,
                7,
                24,
            ),
        )

        progress.full_clean()
        progress.save()

        self.assertTrue(
            progress.is_complete
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
                "started_on": "",
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
                "started_on": "",
                "finished_on": "",
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


