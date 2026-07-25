from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


class MediaWork(models.Model):
    class MediaType(models.TextChoices):
        MOVIE = "movie", "Movie"
        SERIES = "series", "Series"

    class Presentation(models.TextChoices):
        ANIMATION = "animation", "Animation / Cartoon"
        LIVE_ACTION = "live_action", "Live Action"
        DOCUMENTARY = "documentary", "Documentary"
        MIXED = "mixed", "Mixed"
        OTHER = "other", "Other"

    tmdb_id = models.PositiveBigIntegerField(
        blank=True,
        null=True,
    )
    media_type = models.CharField(
        max_length=16,
        choices=MediaType.choices,
    )
    title = models.CharField(
        max_length=255,
        db_index=True,
    )
    original_title = models.CharField(
        max_length=255,
        blank=True,
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        editable=False,
    )
    overview = models.TextField(
        blank=True,
    )
    presentation = models.CharField(
        max_length=24,
        choices=Presentation.choices,
        default=Presentation.LIVE_ACTION,
    )
    original_language = models.CharField(
        max_length=16,
        blank=True,
    )
    first_release_date = models.DateField(
        blank=True,
        null=True,
    )
    runtime_minutes = models.PositiveIntegerField(
        blank=True,
        null=True,
    )
    external_status = models.CharField(
        max_length=64,
        blank=True,
    )
    poster_url = models.URLField(
        max_length=500,
        blank=True,
    )
    backdrop_url = models.URLField(
        max_length=500,
        blank=True,
    )
    genres = models.JSONField(
        default=list,
        blank=True,
    )
    origin_countries = models.JSONField(
        default=list,
        blank=True,
    )
    networks = models.JSONField(
        default=list,
        blank=True,
    )
    tmdb_payload = models.JSONField(
        default=dict,
        blank=True,
    )
    tmdb_synced_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "title",
            "pk",
        )
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "media_type",
                    "tmdb_id",
                ),
                condition=Q(
                    tmdb_id__isnull=False,
                ),
                name=(
                    "watchroom_unique_tmdb_identity"
                ),
            ),
            models.CheckConstraint(
                condition=(
                    Q(tmdb_id__isnull=True)
                    | Q(tmdb_id__gt=0)
                ),
                name=(
                    "watchroom_tmdb_id_positive_or_null"
                ),
            ),
            models.CheckConstraint(
                condition=(
                    Q(runtime_minutes__isnull=True)
                    | Q(runtime_minutes__gt=0)
                ),
                name=(
                    "watchroom_runtime_positive_or_null"
                ),
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        Q(
                            media_type="movie",
                        )
                    )
                    | Q(
                        runtime_minutes__isnull=True,
                    )
                ),
                name=(
                    "watchroom_series_runtime_is_null"
                ),
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()

        if (
            self.media_type
            == self.MediaType.SERIES
            and self.runtime_minutes is not None
        ):
            raise ValidationError(
                {
                    "runtime_minutes": (
                        "Series do not use a universal "
                        "runtime in Watchroom."
                    ),
                }
            )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._build_unique_slug()

        super().save(
            *args,
            **kwargs,
        )

    def _build_unique_slug(self):
        slug_field = self._meta.get_field(
            "slug"
        )
        max_length = slug_field.max_length

        base_slug = slugify(
            self.title
        )

        if not base_slug:
            fallback_id = (
                self.tmdb_id
                if self.tmdb_id is not None
                else "local"
            )
            base_slug = (
                f"{self.media_type}-"
                f"{fallback_id}"
            )

        base_slug = base_slug[
            :max_length
        ]
        candidate = base_slug
        counter = 2

        while (
            MediaWork.objects
            .filter(
                slug=candidate,
            )
            .exclude(
                pk=self.pk,
            )
            .exists()
        ):
            suffix = f"-{counter}"
            available_length = (
                max_length - len(suffix)
            )
            candidate = (
                f"{base_slug[:available_length]}"
                f"{suffix}"
            )
            counter += 1

        return candidate


class Season(models.Model):
    media_work = models.ForeignKey(
        MediaWork,
        on_delete=models.CASCADE,
        related_name="seasons",
    )
    tmdb_id = models.PositiveBigIntegerField(
        blank=True,
        null=True,
    )
    season_number = models.PositiveIntegerField()
    name = models.CharField(
        max_length=255,
        blank=True,
    )
    episode_count = models.PositiveIntegerField(
        default=0,
    )
    air_date = models.DateField(
        blank=True,
        null=True,
    )
    poster_url = models.URLField(
        max_length=500,
        blank=True,
    )
    tmdb_payload = models.JSONField(
        default=dict,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "season_number",
            "pk",
        )
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "media_work",
                    "season_number",
                ),
                name=(
                    "watchroom_unique_season_"
                    "number_per_work"
                ),
            ),
            models.CheckConstraint(
                condition=(
                    Q(tmdb_id__isnull=True)
                    | Q(tmdb_id__gt=0)
                ),
                name=(
                    "watchroom_season_tmdb_id_"
                    "positive_or_null"
                ),
            ),
        ]

    def __str__(self):
        if self.name:
            season_label = self.name
        elif self.is_special:
            season_label = "Specials"
        else:
            season_label = (
                f"Season {self.season_number}"
            )

        return (
            f"{self.media_work.title} "
            f"— {season_label}"
        )

    @property
    def is_special(self):
        return self.season_number == 0

    def clean(self):
        super().clean()

        if (
            self.media_work_id
            and self.media_work.media_type
            != MediaWork.MediaType.SERIES
        ):
            raise ValidationError(
                {
                    "media_work": (
                        "Seasons can only belong "
                        "to series."
                    ),
                }
            )


class WatchEntry(models.Model):
    class Status(models.TextChoices):
        PLAN_TO_WATCH = (
            "plan_to_watch",
            "Plan to Watch",
        )
        WATCHING = "watching", "Watching"
        PAUSED = "paused", "Paused"
        DROPPED = "dropped", "Dropped"
        COMPLETED = "completed", "Completed"

    media_work = models.OneToOneField(
        MediaWork,
        on_delete=models.CASCADE,
        related_name="watch_entry",
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PLAN_TO_WATCH,
        db_index=True,
    )
    notes = models.TextField(
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "-updated_at",
            "-pk",
        )

    def __str__(self):
        return (
            f"{self.media_work.title} "
            f"— {self.get_status_display()}"
        )


class ViewingRun(models.Model):
    class Status(models.TextChoices):
        WATCHING = "watching", "Watching"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        DROPPED = "dropped", "Dropped"

    watch_entry = models.ForeignKey(
        WatchEntry,
        on_delete=models.CASCADE,
        related_name="viewing_runs",
    )
    number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.WATCHING,
        db_index=True,
    )
    started_on = models.DateField(
        blank=True,
        null=True,
    )
    finished_on = models.DateField(
        blank=True,
        null=True,
    )
    progress_minutes = models.PositiveIntegerField(
        blank=True,
        null=True,
    )
    notes = models.TextField(
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "number",
            "pk",
        )
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "watch_entry",
                    "number",
                ),
                name=(
                    "watchroom_unique_run_"
                    "number_per_entry"
                ),
            ),
            models.UniqueConstraint(
                fields=(
                    "watch_entry",
                ),
                condition=Q(
                    status__in=(
                        "watching",
                        "paused",
                    ),
                ),
                name=(
                    "watchroom_one_active_"
                    "run_per_entry"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    number__gt=0,
                ),
                name=(
                    "watchroom_run_number_positive"
                ),
            ),
            models.CheckConstraint(
                condition=(
                    Q(started_on__isnull=True)
                    | Q(finished_on__isnull=True)
                    | Q(
                        finished_on__gte=(
                            models.F("started_on")
                        ),
                    )
                ),
                name=(
                    "watchroom_run_date_range_valid"
                ),
            ),
            models.CheckConstraint(
                condition=(
                    Q(progress_minutes__isnull=True)
                    | Q(progress_minutes__gt=0)
                ),
                name=(
                    "watchroom_run_progress_"
                    "positive_or_null"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.watch_entry.media_work.title} "
            f"— Run {self.number} "
            f"({self.get_status_display()})"
        )

    @property
    def is_rewatch(self):
        return self.number > 1

    @property
    def is_active(self):
        return self.status in {
            self.Status.WATCHING,
            self.Status.PAUSED,
        }

    def clean(self):
        super().clean()

        if not self.watch_entry_id:
            return

        media_work = (
            self.watch_entry.media_work
        )

        if (
            media_work.media_type
            == MediaWork.MediaType.SERIES
            and self.progress_minutes is not None
        ):
            raise ValidationError(
                {
                    "progress_minutes": (
                        "Series progress is tracked "
                        "by season, not by minutes."
                    ),
                }
            )

        if (
            self.progress_minutes is not None
            and media_work.runtime_minutes
            is not None
            and self.progress_minutes
            > media_work.runtime_minutes
        ):
            raise ValidationError(
                {
                    "progress_minutes": (
                        "Movie progress cannot exceed "
                        "the known runtime."
                    ),
                }
            )

        if (
            self.status
            in {
                self.Status.WATCHING,
                self.Status.PAUSED,
            }
            and self.finished_on is not None
        ):
            raise ValidationError(
                {
                    "finished_on": (
                        "An active viewing run cannot "
                        "have a finish date."
                    ),
                }
            )


class SeasonProgress(models.Model):
    viewing_run = models.ForeignKey(
        ViewingRun,
        on_delete=models.CASCADE,
        related_name="season_progress",
    )
    season = models.ForeignKey(
        Season,
        on_delete=models.PROTECT,
        related_name="progress_records",
    )
    episodes_watched = models.PositiveIntegerField(
        default=0,
    )
    started_on = models.DateField(
        blank=True,
        null=True,
    )
    finished_on = models.DateField(
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "season__season_number",
            "pk",
        )
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "viewing_run",
                    "season",
                ),
                name=(
                    "watchroom_unique_season_"
                    "progress_per_run"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    episodes_watched__gte=0,
                ),
                name=(
                    "watchroom_episodes_watched_"
                    "non_negative"
                ),
            ),
            models.CheckConstraint(
                condition=(
                    Q(started_on__isnull=True)
                    | Q(finished_on__isnull=True)
                    | Q(
                        finished_on__gte=(
                            models.F("started_on")
                        ),
                    )
                ),
                name=(
                    "watchroom_season_progress_"
                    "date_range_valid"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.viewing_run} — "
            f"{self.season}: "
            f"{self.episodes_watched} / "
            f"{self.season.episode_count}"
        )

    @property
    def is_complete(self):
        return (
            self.season.episode_count > 0
            and self.episodes_watched
            == self.season.episode_count
        )

    @property
    def display_progress(self):
        return (
            f"{self.episodes_watched} / "
            f"{self.season.episode_count}"
        )

    def clean(self):
        super().clean()

        if (
            not self.viewing_run_id
            or not self.season_id
        ):
            return

        run_work = (
            self.viewing_run
            .watch_entry
            .media_work
        )
        season_work = self.season.media_work

        if (
            run_work.media_type
            != MediaWork.MediaType.SERIES
        ):
            raise ValidationError(
                {
                    "viewing_run": (
                        "Season progress can only "
                        "belong to a series run."
                    ),
                }
            )

        if run_work.pk != season_work.pk:
            raise ValidationError(
                {
                    "season": (
                        "The season and viewing run "
                        "must belong to the same series."
                    ),
                }
            )

        if (
            self.episodes_watched
            > self.season.episode_count
        ):
            raise ValidationError(
                {
                    "episodes_watched": (
                        "Watched episodes cannot exceed "
                        "the season episode count."
                    ),
                }
            )

        if (
            self.finished_on is not None
            and not self.is_complete
        ):
            raise ValidationError(
                {
                    "finished_on": (
                        "A season can only have a finish "
                        "date when all known episodes "
                        "have been watched."
                    ),
                }
            )


