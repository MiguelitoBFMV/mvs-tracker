from django.db import models
from django.utils import timezone

from decimal import (
    Decimal,
    ROUND_FLOOR,
)

class MangaEntry(models.Model):
    # Datos base del manga en MAL
    mal_id = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=255)
    title_japanese = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    title_english = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    main_picture_url = models.URLField(blank=True, null=True)

    media_type = models.CharField(max_length=50, blank=True, null=True)
    publication_status = models.CharField(max_length=50, blank=True, null=True)

    num_volumes = models.PositiveIntegerField(default=0)
    num_chapters = models.PositiveIntegerField(default=0)

    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    # Estado dentro de TU lista MAL
    list_status = models.CharField(max_length=50)
    score = models.PositiveIntegerField(default=0)

    num_volumes_read = models.PositiveIntegerField(default=0)
    num_chapters_read = models.PositiveIntegerField(default=0)

    is_rereading = models.BooleanField(default=False)
    updated_at_mal = models.DateTimeField(blank=True, null=True)

    # Guardamos el JSON original por seguridad/análisis futuro
    raw_data = models.JSONField(blank=True, null=True)

    # Control interno de sincronización
    last_synced_at = models.DateTimeField(default=timezone.now)

    @property
    def display_title(self):
        if self.title_japanese:
            return (
                f"{self.title} "
                f"({self.title_japanese})"
            )

        return self.title

    @property
    def media_type_label(self):
        labels = {
            "manga": "Manga",
            "light_novel": "Light Novel",
            "manhwa": "Manhwa",
            "one_shot": "One-shot",
        }

        return labels.get(
            self.media_type,
            self.media_type or "Unknown",
        )


    @property
    def publication_status_label(self):
        labels = {
            "currently_publishing": (
                "Publishing"
            ),
            "finished": "Finished",
            "on_hiatus": "On Hiatus",
            "discontinued": "Discontinued",
        }

        return labels.get(
            self.publication_status,
            self.publication_status or "Unknown",
        )

    @property
    def personal_status_label(self):
        if self.is_rereading:
            return "Rereading"

        status_labels = {
            "reading": "Reading",
            "completed": "Completed",
            "on_hold": "On hold",
            "dropped": "Dropped",
            "plan_to_read": "Plan to read",
        }

        return status_labels.get(self.list_status, self.list_status)

    class Meta:
        ordering = ["-updated_at_mal", "title"]

    def __str__(self):
        return f"{self.title} ({self.list_status})"


class MangaSyncEvent(models.Model):
    EVENT_TYPES = [
        ("created", "Created"),
        ("status_changed", "Status changed"),
        ("chapter_changed", "Chapter changed"),
        ("volume_changed", "Volume changed"),
        ("score_changed", "Score changed"),
    ]

    manga = models.ForeignKey(
        MangaEntry,
        on_delete=models.CASCADE,
        related_name="sync_events",
        blank=True,
        null=True,
    )
    mal_id = models.PositiveIntegerField()
    title_snapshot = models.CharField(
        max_length=255
    )
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPES,
    )
    old_value = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    new_value = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(
        default=timezone.now
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.title_snapshot} · "
            f"{self.event_type}: "
            f"{self.old_value} → "
            f"{self.new_value}"
        )


class ManualTrackedManga(models.Model):
    STATUS_CHOICES = [
        ("reading", "Reading"),
        ("completed", "Completed"),
        ("on_hold", "On hold"),
        ("dropped", "Dropped"),
        ("plan_to_read", "Plan to read"),
    ]

    mal_id = models.PositiveIntegerField(
        unique=True
    )
    title_snapshot = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
    )
    chapters_read = models.PositiveIntegerField(
        default=0
    )
    volumes_read = models.PositiveIntegerField(
        default=0
    )
    score = models.PositiveIntegerField(
        default=0
    )
    is_rereading = models.BooleanField(
        default=False
    )
    active = models.BooleanField(
        default=True
    )
    notes = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = [
            "title_snapshot",
            "mal_id",
        ]

    def __str__(self):
        return (
            f"{self.title_snapshot or self.mal_id} "
            f"({self.status})"
        )


class MangaSourceLink(models.Model):
    manga = models.ForeignKey(
        MangaEntry,
        on_delete=models.CASCADE,
        related_name="source_links",
    )

    provider = models.CharField(
        max_length=50,
    )
    source_id = models.CharField(
        max_length=255,
    )
    source_title = models.CharField(
        max_length=255,
    )
    source_url = models.URLField(
        max_length=500,
    )
    thumbnail_url = models.URLField(
        max_length=500,
        blank=True,
    )

    match_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    search_query = models.CharField(
        max_length=255,
        blank=True,
    )

    active = models.BooleanField(
        default=True,
    )
    raw_data = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    priority = models.PositiveSmallIntegerField(
        default=1,
    )

    is_official = models.BooleanField(
        default=False,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "manga",
                    "provider",
                ],
                name=(
                    "unique_manga_provider_"
                    "source_link"
                ),
            ),
        ]
        ordering = [
            "manga__title",
            "provider",
        ]

    def __str__(self):
        return (
            f"{self.manga.title} · "
            f"{self.provider}: "
            f"{self.source_title}"
        )


class MangaChapterSignal(models.Model):
    SOURCE_TYPES = [
        (
            "canonical",
            "Canonical total",
        ),
        (
            "external",
            "External source",
        ),
        (
            "manual",
            "Manual",
        ),
    ]

    manga = models.OneToOneField(
        MangaEntry,
        on_delete=models.CASCADE,
        related_name="chapter_signal",
    )
    mal_id = models.PositiveIntegerField(
        unique=True
    )

    # Total canónico conocido por MAL.
    canonical_total_chapters = (
        models.PositiveIntegerField(
            default=0
        )
    )

    # Último capítulo disponible en una
    # fuente externa. Será usado en el
    # siguiente bloque.
    latest_available_chapter = (
        models.DecimalField(
            max_digits=8,
            decimal_places=2,
            blank=True,
            null=True,
        )
    )

    latest_available_changed_at = (
        models.DateTimeField(
            blank=True,
            null=True,
        )
    )

    availability_source_type = (
        models.CharField(
            max_length=30,
            choices=SOURCE_TYPES,
            default="canonical",
        )
    )
    availability_source_name = (
        models.CharField(
            max_length=100,
            blank=True,
        )
    )
    availability_source_url = (
        models.URLField(
            blank=True,
        )
    )

    release_schedule = models.CharField(
        max_length=100,
        blank=True,
    )
    next_release_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    external_checked_at = (
        models.DateTimeField(
            blank=True,
            null=True,
        )
    )

    raw_data = models.JSONField(
        default=dict,
        blank=True,
    )
    last_synced_at = models.DateTimeField(
        default=timezone.now
    )

    @property
    def canonical_target_chapter(self):
        return (
            self.canonical_total_chapters
            or self.manga.num_chapters
            or 0
        )

    @property
    def target_chapter(self):
        if (
            self.latest_available_chapter
            is not None
        ):
            return (
                self.latest_available_chapter
                .to_integral_value(
                    rounding=ROUND_FLOOR
                )
            )

        canonical_total = (
            self.canonical_target_chapter
        )

        if canonical_total <= 0:
            return None

        return Decimal(canonical_total)

    @property
    def chapters_to_complete(self):
        canonical_total = (
            self.canonical_target_chapter
        )

        if canonical_total <= 0:
            return 0

        return max(
            canonical_total
            - self.manga.num_chapters_read,
            0,
        )

    @property
    def pending_chapters(self):
        target = self.target_chapter

        if target is None:
            return Decimal("0")

        pending = (
            target
            - Decimal(
                self.manga.num_chapters_read
            )
        )

        return max(
            pending,
            Decimal("0"),
        )

    @property
    def has_live_availability(self):
        return (
            self.latest_available_chapter
            is not None
        )

    @property
    def has_signal(self):
        return self.pending_chapters > 0

    @property
    def signal_kind(self):
        if self.has_live_availability:
            return "live"

        return "canonical"

    class Meta:
        ordering = [
            "manga__title",
        ]

    def __str__(self):
        return (
            f"{self.manga.title} · "
            f"{self.signal_kind} signal"
        )


class AnimeEntry(models.Model):
    # Datos base del anime en MAL
    mal_id = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=255)
    title_japanese = models.CharField(max_length=255, blank=True, null=True)
    title_english = models.CharField(max_length=255, blank=True, null=True)
    main_picture_url = models.URLField(blank=True, null=True)

    media_type = models.CharField(max_length=50, blank=True, null=True)
    airing_status = models.CharField(max_length=50, blank=True, null=True)

    num_episodes = models.PositiveIntegerField(default=0)

    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    # Estado dentro de TU lista MAL
    list_status = models.CharField(max_length=50)
    score = models.PositiveIntegerField(default=0)

    num_episodes_watched = models.PositiveIntegerField(default=0)
    is_rewatching = models.BooleanField(default=False)

    updated_at_mal = models.DateTimeField(blank=True, null=True)

    # Guardamos el JSON original por seguridad/análisis futuro
    raw_data = models.JSONField(blank=True, null=True)

    # Control interno de sincronización
    last_synced_at = models.DateTimeField(default=timezone.now)

    @property
    def display_title(self):
        if self.title_japanese:
            return f"{self.title} ({self.title_japanese})"

        return self.title

    @property
    def personal_status_label(self):
        if self.is_rewatching:
            return "Rewatching"

        status_labels = {
            "watching": "Watching",
            "completed": "Completed",
            "on_hold": "On hold",
            "dropped": "Dropped",
            "plan_to_watch": "Plan to watch",
        }

        return status_labels.get(self.list_status, self.list_status)

    class Meta:
        ordering = ["-updated_at_mal", "title"]

    def __str__(self):
        return f"{self.title} ({self.list_status})"

class MangaRelation(models.Model):
    source_manga = models.ForeignKey(
        MangaEntry,
        on_delete=models.CASCADE,
        related_name="relations",
        blank=True,
        null=True,
    )

    source_mal_id = (
        models.PositiveIntegerField()
    )

    source_title = models.CharField(
        max_length=255
    )

    target_mal_id = (
        models.PositiveIntegerField()
    )

    target_title = models.CharField(
        max_length=255
    )

    target_media_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    target_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    target_picture_url = models.URLField(
        blank=True,
        null=True,
    )

    target_num_episodes = (
        models.PositiveIntegerField(
            default=0
        )
    )

    target_num_chapters = (
        models.PositiveIntegerField(
            default=0
        )
    )

    target_num_volumes = (
        models.PositiveIntegerField(
            default=0
        )
    )

    relation_type = models.CharField(
        max_length=100
    )

    relation_type_formatted = (
        models.CharField(
            max_length=100,
            blank=True,
            null=True,
        )
    )

    # anime | manga
    relation_source_type = (
        models.CharField(
            max_length=20
        )
    )

    target_local_list_status = (
        models.CharField(
            max_length=50,
            blank=True,
            null=True,
        )
    )

    raw_data = models.JSONField(
        blank=True,
        null=True,
    )

    last_synced_at = models.DateTimeField(
        default=timezone.now
    )

    @property
    def target_anime_entry(self):
        if (
            self.relation_source_type
            != "anime"
        ):
            return None

        return (
            AnimeEntry.objects
            .filter(
                mal_id=self.target_mal_id
            )
            .first()
        )

    @property
    def target_anime_metadata(self):
        if (
            self.relation_source_type
            != "anime"
        ):
            return None

        return (
            AnimeMetadata.objects
            .filter(
                mal_id=self.target_mal_id
            )
            .first()
        )

    @property
    def target_manga_entry(self):
        if (
            self.relation_source_type
            != "manga"
        ):
            return None

        return (
            MangaEntry.objects
            .filter(
                mal_id=self.target_mal_id
            )
            .first()
        )

    @property
    def has_local_target(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            return (
                self.target_anime_entry
                is not None
            )

        if (
            self.relation_source_type
            == "manga"
        ):
            return (
                self.target_manga_entry
                is not None
            )

        return False

    @property
    def target_display_title(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

            if target:
                return (
                    target.display_title
                )

            metadata = (
                self.target_anime_metadata
            )

            if metadata:
                return (
                    metadata.display_title
                )

        elif (
            self.relation_source_type
            == "manga"
        ):
            target = (
                self.target_manga_entry
            )

            if target:
                return (
                    target.display_title
                )

        return self.target_title

    @property
    def target_display_picture_url(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

            if (
                target
                and target.main_picture_url
            ):
                return (
                    target.main_picture_url
                )

            metadata = (
                self.target_anime_metadata
            )

            if (
                metadata
                and metadata.main_picture_url
            ):
                return (
                    metadata.main_picture_url
                )

        elif (
            self.relation_source_type
            == "manga"
        ):
            target = (
                self.target_manga_entry
            )

            if (
                target
                and target.main_picture_url
            ):
                return (
                    target.main_picture_url
                )

        return self.target_picture_url

    @property
    def target_display_status(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

        else:
            target = (
                self.target_manga_entry
            )

        if target:
            return (
                target.personal_status_label
            )

        if self.target_local_list_status:
            return (
                self.target_local_list_status
            )

        return "Not in local list"

    @property
    def target_display_media_type(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

            if (
                target
                and target.media_type
            ):
                return target.media_type

            metadata = (
                self.target_anime_metadata
            )

            if (
                metadata
                and metadata.media_type
            ):
                return (
                    metadata.media_type
                )

        else:
            target = (
                self.target_manga_entry
            )

            if (
                target
                and target.media_type
            ):
                return target.media_type

        return (
            self.target_media_type
            or "-"
        )

    @property
    def target_display_progress(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

            if target:
                total = (
                    target.num_episodes
                    or "TBD"
                )

                return (
                    f"{target.num_episodes_watched}"
                    f"/{total}"
                )

            total = (
                self.target_num_episodes
                or "TBD"
            )

            return f"-/{total}"

        target = (
            self.target_manga_entry
        )

        if target:
            total = (
                target.num_chapters
                or "TBD"
            )

            return (
                f"{target.num_chapters_read}"
                f"/{total}"
            )

        total = (
            self.target_num_chapters
            or "TBD"
        )

        return f"-/{total}"

    @property
    def target_display_score(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

        else:
            target = (
                self.target_manga_entry
            )

        if target:
            return target.score

        return "-"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_mal_id",
                    "target_mal_id",
                    "relation_source_type",
                    "relation_type",
                ],
                name=(
                    "unique_manga_relation"
                ),
            ),
        ]

        ordering = [
            "source_title",
            "relation_source_type",
            "relation_type",
            "target_title",
        ]

    def __str__(self):
        relation_label = (
            self.relation_type_formatted
            or self.relation_type
        )

        return (
            f"{self.source_title} "
            f"→ {relation_label} "
            f"→ {self.target_title}"
        )
    
class AnimeRelation(models.Model):
    source_anime = models.ForeignKey(
        AnimeEntry,
        on_delete=models.CASCADE,
        related_name="relations",
        blank=True,
        null=True,
    )

    source_mal_id = models.PositiveIntegerField()
    source_title = models.CharField(max_length=255)

    target_mal_id = models.PositiveIntegerField()
    target_title = models.CharField(max_length=255)

    target_media_type = models.CharField(max_length=50, blank=True, null=True)
    target_status = models.CharField(max_length=50, blank=True, null=True)
    target_picture_url = models.URLField(blank=True, null=True)

    target_num_episodes = (
        models.PositiveIntegerField(
            default=0
        )
    )

    target_num_chapters = (
        models.PositiveIntegerField(
            default=0
        )
    )

    target_num_volumes = (
        models.PositiveIntegerField(
            default=0
        )
    )

    relation_type = models.CharField(max_length=100)
    relation_type_formatted = models.CharField(max_length=100, blank=True, null=True)

    # anime o manga
    relation_source_type = models.CharField(max_length=20)

    # Si el target existe en tu lista local, lo guardaremos después
    target_local_list_status = models.CharField(max_length=50, blank=True, null=True)

    raw_data = models.JSONField(blank=True, null=True)
    last_synced_at = models.DateTimeField(default=timezone.now)

    @property
    def target_anime_entry(self):
        if (
            self.relation_source_type
            != "anime"
        ):
            return None

        return (
            AnimeEntry.objects
            .filter(
                mal_id=self.target_mal_id
            )
            .first()
        )


    @property
    def target_anime_metadata(self):
        if (
            self.relation_source_type
            != "anime"
        ):
            return None

        return (
            AnimeMetadata.objects
            .filter(
                mal_id=self.target_mal_id
            )
            .first()
        )


    @property
    def target_manga_entry(self):
        if (
            self.relation_source_type
            != "manga"
        ):
            return None

        return (
            MangaEntry.objects
            .filter(
                mal_id=self.target_mal_id
            )
            .first()
        )


    @property
    def has_local_target(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            return (
                self.target_anime_entry
                is not None
            )

        if (
            self.relation_source_type
            == "manga"
        ):
            return (
                self.target_manga_entry
                is not None
            )

        return False


    @property
    def target_display_status(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

        else:
            target = (
                self.target_manga_entry
            )

        if target:
            return (
                target.personal_status_label
            )

        if self.target_local_list_status:
            return (
                self.target_local_list_status
            )

        return "Not in local list"


    @property
    def target_display_media_type(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

            if (
                target
                and target.media_type
            ):
                return target.media_type

            metadata = (
                self.target_anime_metadata
            )

            if (
                metadata
                and metadata.media_type
            ):
                return metadata.media_type

        else:
            target = (
                self.target_manga_entry
            )

            if (
                target
                and target.media_type
            ):
                return target.media_type

        return (
            self.target_media_type
            or "-"
        )


    @property
    def target_display_airing_status(self):
        if (
            self.relation_source_type
            != "anime"
        ):
            return (
                self.target_status
                or "-"
            )

        target = (
            self.target_anime_entry
        )

        if (
            target
            and target.airing_status
        ):
            return target.airing_status

        metadata = (
            self.target_anime_metadata
        )

        if (
            metadata
            and metadata.airing_status
        ):
            return metadata.airing_status

        return (
            self.target_status
            or "-"
        )


    @property
    def target_display_progress(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

            if target:
                total = (
                    target.num_episodes
                    or "TBD"
                )

                return (
                    f"{target.num_episodes_watched}"
                    f"/{total}"
                )

            total = (
                self.target_num_episodes
                or "TBD"
            )

            return f"-/{total}"

        target = (
            self.target_manga_entry
        )

        if target:
            total = (
                target.num_chapters
                or "TBD"
            )

            return (
                f"{target.num_chapters_read}"
                f"/{total}"
            )

        total = (
            self.target_num_chapters
            or "TBD"
        )

        return f"-/{total}"


    @property
    def target_display_score(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

        else:
            target = (
                self.target_manga_entry
            )

        if target:
            return target.score

        return "-"


    @property
    def target_display_title(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

            if target:
                return (
                    target.display_title
                )

            metadata = (
                self.target_anime_metadata
            )

            if metadata:
                return (
                    metadata.display_title
                )

        else:
            target = (
                self.target_manga_entry
            )

            if target:
                return (
                    target.display_title
                )

        return self.target_title


    @property
    def target_display_picture_url(self):
        if (
            self.relation_source_type
            == "anime"
        ):
            target = (
                self.target_anime_entry
            )

            if (
                target
                and target.main_picture_url
            ):
                return (
                    target.main_picture_url
                )

            metadata = (
                self.target_anime_metadata
            )

            if (
                metadata
                and metadata.main_picture_url
            ):
                return (
                    metadata.main_picture_url
                )

        else:
            target = (
                self.target_manga_entry
            )

            if (
                target
                and target.main_picture_url
            ):
                return (
                    target.main_picture_url
                )

        return self.target_picture_url


    @property
    def is_external_metadata_node(self):
        return (
            self.relation_source_type
            == "anime"
            and self.target_anime_entry
            is None
            and self.target_anime_metadata
            is not None
        )

    class Meta:
        unique_together = (
            "source_mal_id",
            "target_mal_id",
            "relation_source_type",
            "relation_type",
        )
        ordering = ["source_title", "relation_source_type", "relation_type", "target_title"]

    def __str__(self):
        return f"{self.source_title} → {self.relation_type_formatted or self.relation_type} → {self.target_title}"
    
class AnimeSyncEvent(models.Model):
    EVENT_TYPES = [
        ("created", "Created"),
        ("status_changed", "Status changed"),
        ("episode_changed", "Episode changed"),
        ("score_changed", "Score changed"),
    ]

    anime = models.ForeignKey(
        AnimeEntry,
        on_delete=models.CASCADE,
        related_name="sync_events",
        blank=True,
        null=True,
    )
    mal_id = models.PositiveIntegerField()
    title_snapshot = models.CharField(max_length=255)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    old_value = models.CharField(max_length=100, blank=True, null=True)
    new_value = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title_snapshot} · {self.event_type}: {self.old_value} → {self.new_value}"

class AnimeAiringData(models.Model):
    anime = models.OneToOneField(
        AnimeEntry,
        on_delete=models.CASCADE,
        related_name="airing_data",
    )
    mal_id = models.PositiveIntegerField(unique=True)
    anilist_id = models.PositiveIntegerField(blank=True, null=True)

    title_romaji = models.CharField(max_length=255, blank=True, null=True)
    title_english = models.CharField(max_length=255, blank=True, null=True)
    title_native = models.CharField(max_length=255, blank=True, null=True)

    anilist_status = models.CharField(max_length=50, blank=True, null=True)
    anilist_episodes = models.PositiveIntegerField(default=0)

    next_airing_episode = models.PositiveIntegerField(blank=True, null=True)
    next_airing_at = models.DateTimeField(blank=True, null=True)
    time_until_airing_seconds = models.PositiveIntegerField(blank=True, null=True)

    episodes_aired_estimated = models.PositiveIntegerField(default=0)

    streaming_links = models.JSONField(default=list, blank=True)
    streaming_episodes = models.JSONField(default=list, blank=True)

    raw_data = models.JSONField(blank=True, null=True)
    last_synced_at = models.DateTimeField(default=timezone.now)

    @property
    def pending_episodes_for_user(self):
        pending = self.episodes_aired_estimated - self.anime.num_episodes_watched
        return max(pending, 0)

    @property
    def has_episode_signal(self):
        return self.pending_episodes_for_user > 0

    def __str__(self):
        return f"{self.anime.title} · AniList airing data"
    
class ManualTrackedAnime(models.Model):
    STATUS_CHOICES = [
        ("watching", "Watching"),
        ("completed", "Completed"),
        ("on_hold", "On hold"),
        ("dropped", "Dropped"),
        ("plan_to_watch", "Plan to watch"),
    ]

    mal_id = models.PositiveIntegerField(unique=True)
    title_snapshot = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    episodes_watched = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)
    is_rewatching = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title_snapshot", "mal_id"]

    def __str__(self):
        title = self.title_snapshot or f"MAL ID {self.mal_id}"
        return f"{title} ({self.status})"

class AnimeMetadata(models.Model):
    mal_id = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=255)
    title_japanese = models.CharField(max_length=255, blank=True)
    title_english = models.CharField(max_length=255, blank=True)
    main_picture_url = models.URLField(blank=True)

    media_type = models.CharField(max_length=50, blank=True)
    airing_status = models.CharField(max_length=50, blank=True)
    num_episodes = models.PositiveIntegerField(default=0)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    raw_data = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} ({self.mal_id})"

    @property
    def display_title(self):
        return self.title_english or self.title or self.title_japanese or f"MAL #{self.mal_id}"

class SeasonalAnime(models.Model):
    anilist_id = models.PositiveIntegerField(unique=True)
    mal_id = models.PositiveIntegerField(blank=True, null=True)

    title_romaji = models.CharField(max_length=255)
    title_english = models.CharField(max_length=255, blank=True)
    title_native = models.CharField(max_length=255, blank=True)

    cover_image_url = models.URLField(blank=True)

    season = models.CharField(max_length=20)
    season_year = models.PositiveIntegerField()

    format = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=50, blank=True)
    episodes = models.PositiveIntegerField(default=0)

    next_airing_episode = models.PositiveIntegerField(blank=True, null=True)
    next_airing_at = models.DateTimeField(blank=True, null=True)

    genres = models.JSONField(default=list, blank=True)
    studios = models.JSONField(default=list, blank=True)
    external_links = models.JSONField(default=list, blank=True)

    raw_data = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(default=timezone.now)

    @property
    def display_title(self):
        return self.title_english or self.title_romaji or self.title_native or f"AniList #{self.anilist_id}"

class MALOAuthToken(models.Model):
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_type = models.CharField(max_length=30, default="Bearer")
    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    def __str__(self):
        return f"MyAnimeList OAuth · expires {self.expires_at}"

