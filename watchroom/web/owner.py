from django.contrib.auth.decorators import (
    login_required,
)
from django.db import transaction
from django.db.models.deletion import (
    ProtectedError,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_POST,
)

from watchroom.forms import (
    ManualMediaWorkOwnerForm,
    SeasonOwnerForm,
    WatchEntryOwnerForm,
)
from watchroom.models import (
    MediaWork,
    Season,
    ViewingRun,
    WatchEntry,
)

from .detail import render_detail


@login_required
def create_work(request):
    if request.method == "POST":
        form = ManualMediaWorkOwnerForm(
            request.POST,
        )

        if form.is_valid():
            status = form.cleaned_data[
                "status"
            ]
            notes = form.cleaned_data[
                "notes"
            ]

            with transaction.atomic():
                work = form.save()

                entry = WatchEntry.objects.create(
                    media_work=work,
                    status=status,
                    notes=notes,
                )

                historical_run_status = {
                    WatchEntry.Status.COMPLETED: (
                        ViewingRun.Status.COMPLETED
                    ),
                    WatchEntry.Status.DROPPED: (
                        ViewingRun.Status.DROPPED
                    ),
                }.get(status)

                if historical_run_status:
                    ViewingRun.objects.create(
                        watch_entry=entry,
                        number=1,
                        status=historical_run_status,
                    )

            return redirect(
                work.get_absolute_url()
            )
    else:
        form = ManualMediaWorkOwnerForm()

    return render(
        request,
        "watchroom/create_work.html",
        {
            "active_page": "library",
            "form": form,
        },
    )


@login_required
@require_POST
def update_entry(
    request,
    slug,
):
    entry = get_object_or_404(
        WatchEntry.objects.select_related(
            "media_work"
        ),
        media_work__slug=slug,
    )

    form = WatchEntryOwnerForm(
        request.POST,
        instance=entry,
        prefix="entry",
    )

    if form.is_valid():
        form.save()

        return redirect(
            f"{entry.media_work.get_absolute_url()}"
            "#owner-controls"
        )

    return render_detail(
        request,
        slug,
        entry_form=form,
    )


@login_required
@require_POST
def create_season(
    request,
    slug,
):
    work = get_object_or_404(
        MediaWork,
        slug=slug,
        media_type=(
            MediaWork.MediaType.SERIES
        ),
    )

    form = SeasonOwnerForm(
        request.POST,
        media_work=work,
        prefix="new-season",
    )

    if form.is_valid():
        form.save()

        return redirect(
            f"{work.get_absolute_url()}"
            "#season-management"
        )

    return render_detail(
        request,
        slug,
        new_season_form=form,
    )


@login_required
@require_POST
def update_season(
    request,
    slug,
    season_id,
):
    season = get_object_or_404(
        Season.objects.select_related(
            "media_work"
        ),
        pk=season_id,
        media_work__slug=slug,
    )

    form = SeasonOwnerForm(
        request.POST,
        instance=season,
        media_work=season.media_work,
        prefix=f"season-{season.pk}",
    )

    if form.is_valid():
        form.save()

        return redirect(
            f"{season.media_work.get_absolute_url()}"
            "#season-management"
        )

    return render_detail(
        request,
        slug,
        season_update_form=form,
    )


@login_required
@require_POST
def delete_season(
    request,
    slug,
    season_id,
):
    season = get_object_or_404(
        Season.objects.select_related(
            "media_work"
        ),
        pk=season_id,
        media_work__slug=slug,
    )

    work_url = (
        season.media_work.get_absolute_url()
    )

    try:
        season.delete()
    except ProtectedError:
        return render_detail(
            request,
            slug,
            season_action_error=(
                "This season cannot be deleted "
                "because viewing progress already "
                "references it."
            ),
            season_action_id=season_id,
        )

    return redirect(
        f"{work_url}#season-management"
    )