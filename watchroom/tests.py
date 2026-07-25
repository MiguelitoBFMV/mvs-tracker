from datetime import date

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

from django.test import TestCase

from .models import (
    MediaWork,
    Season,
    SeasonProgress,
    ViewingRun,
    WatchEntry,
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


