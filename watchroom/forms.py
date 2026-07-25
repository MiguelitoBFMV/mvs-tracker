from django import forms
from django.utils import timezone
from django.db.models import Max

from .models import (
    MediaWork,
    Season,
    SeasonProgress,
    ViewingRun,
    WatchEntry,
)


ACTIVE_RUN_STATUSES = (
    ViewingRun.Status.WATCHING,
    ViewingRun.Status.PAUSED,
)


class ManualMediaWorkOwnerForm(
    forms.ModelForm
):
    status = forms.ChoiceField(
        choices=WatchEntry.Status.choices,
        initial=(
            WatchEntry.Status.PLAN_TO_WATCH
        ),
        label="Initial Status",
        widget=forms.Select(
            attrs={
                "class": "watchroom-owner-control",
            },
        ),
    )
    notes = forms.CharField(
        required=False,
        label="Library Notes",
        widget=forms.Textarea(
            attrs={
                "class": (
                    "watchroom-owner-control "
                    "watchroom-owner-textarea"
                ),
                "rows": 4,
                "placeholder": (
                    "Personal context, priority "
                    "or viewing notes..."
                ),
            },
        ),
    )

    class Meta:
        model = MediaWork
        fields = (
            "media_type",
            "title",
            "original_title",
            "presentation",
            "overview",
            "original_language",
            "first_release_date",
            "runtime_minutes",
            "external_status",
            "poster_url",
            "backdrop_url",
        )
        labels = {
            "media_type": "Type",
            "title": "Title",
            "original_title": "Original Title",
            "presentation": "Presentation",
            "overview": "Overview",
            "original_language": (
                "Original Language"
            ),
            "first_release_date": (
                "Release Date / First Aired"
            ),
            "runtime_minutes": (
                "Movie Runtime"
            ),
            "external_status": (
                "External Status"
            ),
            "poster_url": "Poster URL",
            "backdrop_url": "Backdrop URL",
        }
        widgets = {
            "media_type": forms.Select(
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                },
            ),
            "title": forms.TextInput(
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                    "placeholder": (
                        "Phineas and Ferb or Saw"
                    ),
                },
            ),
            "original_title": forms.TextInput(
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                    "placeholder": (
                        "Optional original title"
                    ),
                },
            ),
            "presentation": forms.Select(
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                },
            ),
            "overview": forms.Textarea(
                attrs={
                    "class": (
                        "watchroom-owner-control "
                        "watchroom-owner-textarea"
                    ),
                    "rows": 5,
                    "placeholder": (
                        "Optional local synopsis..."
                    ),
                },
            ),
            "original_language": (
                forms.TextInput(
                    attrs={
                        "class": (
                            "watchroom-owner-control"
                        ),
                        "placeholder": (
                            "en, es, ja..."
                        ),
                    },
                )
            ),
            "first_release_date": (
                forms.DateInput(
                    format="%Y-%m-%d",
                    attrs={
                        "class": (
                            "watchroom-owner-control"
                        ),
                        "type": "date",
                    },
                )
            ),
            "runtime_minutes": (
                forms.NumberInput(
                    attrs={
                        "class": (
                            "watchroom-owner-control"
                        ),
                        "min": 1,
                        "step": 1,
                        "placeholder": (
                            "Movies only"
                        ),
                    },
                )
            ),
            "external_status": (
                forms.TextInput(
                    attrs={
                        "class": (
                            "watchroom-owner-control"
                        ),
                        "placeholder": (
                            "Ended, Returning Series..."
                        ),
                    },
                )
            ),
            "poster_url": forms.URLInput(
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                    "placeholder": (
                        "https://..."
                    ),
                },
            ),
            "backdrop_url": forms.URLInput(
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                    "placeholder": (
                        "https://..."
                    ),
                },
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        media_type = cleaned_data.get(
            "media_type"
        )
        runtime_minutes = cleaned_data.get(
            "runtime_minutes"
        )

        if (
            media_type
            == MediaWork.MediaType.SERIES
            and runtime_minutes is not None
        ):
            self.add_error(
                "runtime_minutes",
                (
                    "Series progress is tracked "
                    "by season and does not use "
                    "a universal runtime."
                ),
            )

        status = cleaned_data.get(
            "status"
        )

        if status in {
            WatchEntry.Status.WATCHING,
            WatchEntry.Status.PAUSED,
        }:
            self.add_error(
                "status",
                (
                    "Watching and Paused require a "
                    "viewing run. Create the work first "
                    "and then start a run."
                ),
            )

        return cleaned_data


class WatchEntryOwnerForm(forms.ModelForm):
    class Meta:
        model = WatchEntry
        fields = (
            "status",
            "notes",
        )
        labels = {
            "status": "Library Status",
            "notes": "Library Notes",
        }
        widgets = {
            "status": forms.Select(
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                },
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "watchroom-owner-control "
                        "watchroom-owner-textarea"
                    ),
                    "rows": 4,
                    "placeholder": (
                        "Personal context, priority "
                        "or viewing notes..."
                    ),
                },
            ),
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.has_viewing_runs = bool(
            self.instance.pk
            and self.instance
            .viewing_runs
            .exists()
        )

        if self.has_viewing_runs:
            self.fields["status"].disabled = True
            self.fields["status"].help_text = (
                "This status is controlled by "
                "viewing-run history."
            )
        else:
            self.fields["status"].help_text = (
                "Watching and Paused require "
                "an active viewing run."
            )

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")

        if (
            not self.has_viewing_runs
            and status
            in {
                WatchEntry.Status.WATCHING,
                WatchEntry.Status.PAUSED,
            }
        ):
            self.add_error(
                "status",
                (
                    "Watching and Paused require "
                    "a viewing run. Start one from "
                    "the viewing controls."
                ),
            )

        return cleaned_data


class SeasonOwnerForm(forms.ModelForm):
    class Meta:
        model = Season
        fields = (
            "season_number",
            "name",
            "episode_count",
            "air_date",
            "poster_url",
        )
        labels = {
            "season_number": "Season Number",
            "name": "Season Name",
            "episode_count": "Episode Count",
            "air_date": "Air Date",
            "poster_url": "Poster URL",
        }
        widgets = {
            "season_number": (
                forms.NumberInput(
                    attrs={
                        "class": (
                            "watchroom-owner-control"
                        ),
                        "min": 0,
                    },
                )
            ),
            "name": forms.TextInput(
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                    "placeholder": (
                        "Season 1 or Specials"
                    ),
                },
            ),
            "episode_count": (
                forms.NumberInput(
                    attrs={
                        "class": (
                            "watchroom-owner-control"
                        ),
                        "min": 0,
                    },
                )
            ),
            "air_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                    "type": "date",
                },
            ),
            "poster_url": forms.URLInput(
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                    "placeholder": "https://...",
                },
            ),
        }

    def __init__(
        self,
        *args,
        media_work,
        **kwargs,
    ):
        self.media_work = media_work

        super().__init__(
            *args,
            **kwargs,
        )

        self.instance.media_work = media_work

    def clean(self):
        cleaned_data = super().clean()

        if (
            self.media_work.media_type
            != MediaWork.MediaType.SERIES
        ):
            raise forms.ValidationError(
                (
                    "Seasons can only be added "
                    "to series."
                )
            )

        season_number = cleaned_data.get(
            "season_number"
        )

        if season_number is not None:
            duplicate_season = (
                Season.objects.filter(
                    media_work=self.media_work,
                    season_number=season_number,
                )
            )

            if self.instance.pk:
                duplicate_season = (
                    duplicate_season.exclude(
                        pk=self.instance.pk,
                    )
                )

            if duplicate_season.exists():
                self.add_error(
                    "season_number",
                    (
                        "This season number is "
                        "already registered."
                    ),
                )
        episode_count = cleaned_data.get(
            "episode_count"
        )

        if (
            self.instance.pk
            and episode_count is not None
        ):
            highest_progress = (
                self.instance
                .progress_records
                .aggregate(
                    highest=Max(
                        "episodes_watched"
                    ),
                )["highest"]
                or 0
            )

            if episode_count < highest_progress:
                self.add_error(
                    "episode_count",
                    (
                        "Episode count cannot be lower "
                        f"than the existing progress "
                        f"of {highest_progress}."
                    ),
                )

        return cleaned_data


class NewViewingRunOwnerForm(
    forms.ModelForm
):
    class Meta:
        model = ViewingRun
        fields = (
            "started_on",
            "progress_minutes",
            "notes",
        )
        labels = {
            "started_on": "Started On",
            "progress_minutes": (
                "Movie Progress"
            ),
            "notes": "Run Notes",
        }
        widgets = {
            "started_on": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                    "type": "date",
                },
            ),
            "progress_minutes": (
                forms.NumberInput(
                    attrs={
                        "class": (
                            "watchroom-owner-control"
                        ),
                        "min": 1,
                        "step": 1,
                        "placeholder": (
                            "Movies only"
                        ),
                    },
                )
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "watchroom-owner-control "
                        "watchroom-owner-textarea"
                    ),
                    "rows": 3,
                    "placeholder": (
                        "Rewatch context, plans "
                        "or initial impressions..."
                    ),
                },
            ),
        }

    def __init__(
        self,
        *args,
        watch_entry,
        **kwargs,
    ):
        self.watch_entry = watch_entry

        super().__init__(
            *args,
            **kwargs,
        )

        self.instance.watch_entry = (
            watch_entry
        )

        if (
            watch_entry.media_work.media_type
            == MediaWork.MediaType.SERIES
        ):
            self.fields[
                "progress_minutes"
            ].disabled = True
            self.fields[
                "progress_minutes"
            ].help_text = (
                "Series progress is updated "
                "by season."
            )

        if (
            not self.is_bound
            and not self.instance.pk
        ):
            self.fields[
                "started_on"
            ].initial = timezone.localdate()

    def clean(self):
        cleaned_data = super().clean()

        has_active_run = (
            self.watch_entry
            .viewing_runs
            .filter(
                status__in=(
                    ACTIVE_RUN_STATUSES
                ),
            )
            .exists()
        )

        if has_active_run:
            raise forms.ValidationError(
                (
                    "This work already has an "
                    "active or paused viewing run."
                )
            )

        progress_minutes = cleaned_data.get(
            "progress_minutes"
        )
        work = self.watch_entry.media_work

        if (
            work.media_type
            == MediaWork.MediaType.SERIES
            and progress_minutes is not None
        ):
            self.add_error(
                "progress_minutes",
                (
                    "Series progress must be "
                    "updated by season."
                ),
            )

        if (
            progress_minutes is not None
            and work.runtime_minutes is not None
            and progress_minutes
            > work.runtime_minutes
        ):
            self.add_error(
                "progress_minutes",
                (
                    "Movie progress cannot exceed "
                    f"{work.runtime_minutes} minutes."
                ),
            )

        return cleaned_data


class ViewingRunOwnerForm(
    forms.ModelForm
):
    class Meta:
        model = ViewingRun
        fields = (
            "started_on",
            "finished_on",
            "progress_minutes",
            "notes",
        )
        labels = {
            "started_on": "Started On",
            "finished_on": "Finished On",
            "progress_minutes": (
                "Movie Progress"
            ),
            "notes": "Run Notes",
        }
        widgets = {
            "started_on": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                    "type": "date",
                },
            ),
            "finished_on": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": (
                        "watchroom-owner-control"
                    ),
                    "type": "date",
                },
            ),
            "progress_minutes": (
                forms.NumberInput(
                    attrs={
                        "class": (
                            "watchroom-owner-control"
                        ),
                        "min": 1,
                        "step": 1,
                    },
                )
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "watchroom-owner-control "
                        "watchroom-owner-textarea"
                    ),
                    "rows": 3,
                },
            ),
        }

    def __init__(
        self,
        *args,
        watch_entry,
        **kwargs,
    ):
        self.watch_entry = watch_entry

        super().__init__(
            *args,
            **kwargs,
        )

        if (
            watch_entry.media_work.media_type
            == MediaWork.MediaType.SERIES
        ):
            self.fields[
                "progress_minutes"
            ].disabled = True
            self.fields[
                "progress_minutes"
            ].help_text = (
                "Series progress is updated "
                "by season."
            )

    def clean(self):
        cleaned_data = super().clean()

        if (
            self.instance.watch_entry_id
            != self.watch_entry.pk
        ):
            raise forms.ValidationError(
                (
                    "This viewing run does not "
                    "belong to this work."
                )
            )

        progress_minutes = cleaned_data.get(
            "progress_minutes"
        )
        work = self.watch_entry.media_work

        if (
            progress_minutes is not None
            and work.runtime_minutes is not None
            and progress_minutes
            > work.runtime_minutes
        ):
            self.add_error(
                "progress_minutes",
                (
                    "Movie progress cannot exceed "
                    f"{work.runtime_minutes} minutes."
                ),
            )

        return cleaned_data


class SeasonProgressOwnerForm(
    forms.ModelForm
):
    class Meta:
        model = SeasonProgress
        fields = (
            "episodes_watched",
        )
        labels = {
            "episodes_watched": (
                "Episodes Watched"
            ),
        }
        widgets = {
            "episodes_watched": (
                forms.NumberInput(
                    attrs={
                        "class": (
                            "watchroom-owner-control"
                        ),
                        "min": 0,
                        "step": 1,
                    },
                )
            ),
        }

    def __init__(
        self,
        *args,
        viewing_run,
        season,
        **kwargs,
    ):
        self.viewing_run = viewing_run
        self.season = season

        super().__init__(
            *args,
            **kwargs,
        )

        self.instance.viewing_run = (
            viewing_run
        )
        self.instance.season = season

        self.fields[
            "episodes_watched"
        ].widget.attrs["max"] = (
            season.episode_count
        )

    def clean(self):
        cleaned_data = super().clean()

        run_work = (
            self.viewing_run
            .watch_entry
            .media_work
        )

        if (
            run_work.pk
            != self.season.media_work_id
        ):
            raise forms.ValidationError(
                (
                    "The selected season and "
                    "viewing run belong to "
                    "different series."
                )
            )

        if (
            run_work.media_type
            != MediaWork.MediaType.SERIES
        ):
            raise forms.ValidationError(
                (
                    "Movie runs do not use "
                    "season progress."
                )
            )

        episodes_watched = cleaned_data.get(
            "episodes_watched"
        )

        if (
            episodes_watched is not None
            and episodes_watched
            > self.season.episode_count
        ):
            self.add_error(
                "episodes_watched",
                (
                    "Watched episodes cannot "
                    f"exceed "
                    f"{self.season.episode_count}."
                ),
            )

        return cleaned_data


