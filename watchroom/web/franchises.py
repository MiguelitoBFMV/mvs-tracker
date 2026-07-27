from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
)
from django.db.models import Prefetch
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_POST,
)

from watchroom.forms import (
    FranchiseMembershipOwnerForm,
    FranchiseOwnerForm,
)
from watchroom.models import (
    Franchise,
    FranchiseMembership,
    MediaWork,
    WatchEntry,
)


def _membership_queryset():
    return (
        FranchiseMembership.objects
        .select_related(
            "media_work",
            "media_work__watch_entry",
        )
        .order_by(
            "position",
            "pk",
        )
    )


def _franchise_queryset():
    return (
        Franchise.objects
        .prefetch_related(
            Prefetch(
                "memberships",
                queryset=(
                    _membership_queryset()
                ),
            )
        )
        .order_by(
            "name",
            "pk",
        )
    )


def _decorate_franchise(
    franchise,
):
    memberships = list(
        franchise.memberships.all()
    )

    franchise.member_items = memberships
    franchise.member_count = len(
        memberships
    )
    franchise.movie_count = sum(
        membership.media_work.media_type
        == MediaWork.MediaType.MOVIE
        for membership in memberships
    )
    franchise.series_count = sum(
        membership.media_work.media_type
        == MediaWork.MediaType.SERIES
        for membership in memberships
    )
    franchise.completed_count = sum(
        (
            membership
            .media_work
            .watch_entry
            .status
            == WatchEntry.Status.COMPLETED
        )
        for membership in memberships
    )

    for membership in memberships:
        membership.entry = (
            membership
            .media_work
            .watch_entry
        )

    return franchise


def _render_franchise_detail(
    request,
    franchise,
    *,
    franchise_form=None,
    new_membership_form=None,
    active_membership_id=None,
    active_membership_form=None,
):
    franchise = _decorate_franchise(
        franchise
    )

    if franchise_form is None:
        franchise_form = (
            FranchiseOwnerForm(
                instance=franchise,
                prefix="franchise",
            )
        )

    if new_membership_form is None:
        new_membership_form = (
            FranchiseMembershipOwnerForm(
                franchise=franchise,
                prefix="new-member",
            )
        )

    for membership in (
        franchise.member_items
    ):
        if (
            membership.pk
            == active_membership_id
            and active_membership_form
            is not None
        ):
            membership.owner_form = (
                active_membership_form
            )
        else:
            membership.owner_form = (
                FranchiseMembershipOwnerForm(
                    instance=membership,
                    franchise=franchise,
                    prefix=(
                        f"member-"
                        f"{membership.pk}"
                    ),
                )
            )

    return render(
        request,
        "watchroom/franchise_detail.html",
        {
            "active_page": "franchises",
            "franchise": franchise,
            "franchise_form": (
                franchise_form
            ),
            "new_membership_form": (
                new_membership_form
            ),
        },
    )


def franchise_index(request):
    franchises = [
        _decorate_franchise(franchise)
        for franchise in (
            _franchise_queryset()
        )
    ]

    return render(
        request,
        "watchroom/franchise_index.html",
        {
            "active_page": "franchises",
            "franchises": franchises,
            "franchise_count": len(
                franchises
            ),
        },
    )


def franchise_detail(
    request,
    slug,
):
    franchise = get_object_or_404(
        _franchise_queryset(),
        slug=slug,
    )

    return _render_franchise_detail(
        request,
        franchise,
    )


@login_required
def create_franchise(request):
    form = FranchiseOwnerForm(
        request.POST or None,
        prefix="franchise",
    )

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        franchise = form.save()

        messages.success(
            request,
            "Franchise created.",
        )

        return redirect(
            franchise.get_absolute_url()
        )

    return render(
        request,
        "watchroom/franchise_create.html",
        {
            "active_page": "franchises",
            "form": form,
        },
    )


@login_required
@require_POST
def update_franchise(
    request,
    slug,
):
    franchise = get_object_or_404(
        _franchise_queryset(),
        slug=slug,
    )

    form = FranchiseOwnerForm(
        request.POST,
        instance=franchise,
        prefix="franchise",
    )

    if form.is_valid():
        form.save()

        messages.success(
            request,
            "Franchise details updated.",
        )

        return redirect(
            franchise.get_absolute_url()
        )

    return _render_franchise_detail(
        request,
        franchise,
        franchise_form=form,
    )


@login_required
@require_POST
def delete_franchise(
    request,
    slug,
):
    franchise = get_object_or_404(
        Franchise,
        slug=slug,
    )

    if franchise.memberships.exists():
        messages.error(
            request,
            (
                "Remove every work before "
                "deleting this franchise."
            ),
        )

        return redirect(
            franchise.get_absolute_url()
        )

    franchise.delete()

    messages.success(
        request,
        "Franchise deleted.",
    )

    return redirect(
        "watchroom:franchise_index"
    )


@login_required
@require_POST
def add_franchise_member(
    request,
    slug,
):
    franchise = get_object_or_404(
        _franchise_queryset(),
        slug=slug,
    )

    form = (
        FranchiseMembershipOwnerForm(
            request.POST,
            franchise=franchise,
            prefix="new-member",
        )
    )

    if form.is_valid():
        membership = form.save()

        messages.success(
            request,
            (
                f"{membership.media_work.title} "
                "added to the franchise."
            ),
        )

        return redirect(
            franchise.get_absolute_url()
        )

    return _render_franchise_detail(
        request,
        franchise,
        new_membership_form=form,
    )


@login_required
@require_POST
def update_franchise_member(
    request,
    slug,
    membership_id,
):
    franchise = get_object_or_404(
        _franchise_queryset(),
        slug=slug,
    )
    membership = get_object_or_404(
        FranchiseMembership,
        pk=membership_id,
        franchise=franchise,
    )

    form = (
        FranchiseMembershipOwnerForm(
            request.POST,
            instance=membership,
            franchise=franchise,
            prefix=(
                f"member-{membership.pk}"
            ),
        )
    )

    if form.is_valid():
        form.save()

        messages.success(
            request,
            "Franchise membership updated.",
        )

        return redirect(
            franchise.get_absolute_url()
        )

    return _render_franchise_detail(
        request,
        franchise,
        active_membership_id=(
            membership.pk
        ),
        active_membership_form=form,
    )


@login_required
@require_POST
def remove_franchise_member(
    request,
    slug,
    membership_id,
):
    franchise = get_object_or_404(
        Franchise,
        slug=slug,
    )
    membership = get_object_or_404(
        FranchiseMembership,
        pk=membership_id,
        franchise=franchise,
    )

    work_title = (
        membership.media_work.title
    )
    membership.delete()

    messages.success(
        request,
        (
            f"{work_title} removed from "
            "the franchise."
        ),
    )

    return redirect(
        franchise.get_absolute_url()
    )


