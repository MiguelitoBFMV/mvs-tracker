from django.contrib.auth.decorators import (
    login_required,
)
from django.http import Http404
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.contrib import messages

from django.views.decorators.http import (
    require_POST,
)

from watchroom.forms import (
    TMDBImportForm,
    TMDBSearchForm,
)
from watchroom.models import MediaWork
from watchroom.services.tmdb_client import (
    TMDBClient,
    TMDBClientError,
)
from watchroom.services.tmdb_importer import (
    TMDBDuplicateWorkError,
    TMDBImportError,
    fetch_tmdb_details,
    import_tmdb_work,
)
from watchroom.services.tmdb_normalizer import (
    TMDBNormalizationError,
    normalize_movie_search_result,
    normalize_series_search_result,
)

from watchroom.services.tmdb_refresh import (
    TMDBRefreshError,
    refresh_work_from_tmdb,
)


@login_required
def search_tmdb(request):
    form = TMDBSearchForm(
        request.GET or None
    )

    results = []
    searched = False
    search_error = ""

    if form.is_bound and form.is_valid():
        searched = True

        media_type = (
            form.cleaned_data[
                "media_type"
            ]
        )
        query = form.cleaned_data[
            "query"
        ]

        try:
            client = TMDBClient()

            if (
                media_type
                == MediaWork.MediaType.MOVIE
            ):
                raw_results = (
                    client.search_movie(
                        query,
                        limit=12,
                    )
                )
                normalizer = (
                    normalize_movie_search_result
                )
            else:
                raw_results = (
                    client.search_series(
                        query,
                        limit=12,
                    )
                )
                normalizer = (
                    normalize_series_search_result
                )

            for payload in raw_results:
                try:
                    result = normalizer(
                        payload
                    )
                except TMDBNormalizationError:
                    continue

                results.append(result)

            result_ids = [
                result["tmdb_id"]
                for result in results
            ]

            existing_works = {
                work.tmdb_id: work
                for work in (
                    MediaWork.objects.filter(
                        media_type=media_type,
                        tmdb_id__in=result_ids,
                    )
                )
            }

            for result in results:
                local_work = (
                    existing_works.get(
                        result["tmdb_id"]
                    )
                )

                result["is_imported"] = (
                    local_work is not None
                )
                result["local_url"] = (
                    local_work.get_absolute_url()
                    if local_work is not None
                    else ""
                )

        except TMDBClientError as error:
            search_error = str(error)

    context = {
        "active_page": "tmdb_search",
        "form": form,
        "results": results,
        "searched": searched,
        "search_error": search_error,
    }

    return render(
        request,
        "watchroom/tmdb_search.html",
        context,
    )


def _valid_route_media_type(
    media_type,
):
    if media_type not in {
        MediaWork.MediaType.MOVIE,
        MediaWork.MediaType.SERIES,
    }:
        raise Http404(
            "Unsupported TMDB media type."
        )

    return media_type


@login_required
def review_tmdb_import(
    request,
    media_type,
    tmdb_id,
):
    media_type = _valid_route_media_type(
        media_type
    )

    existing_work = (
        MediaWork.objects.filter(
            media_type=media_type,
            tmdb_id=tmdb_id,
        )
        .first()
    )

    if existing_work is not None:
        return redirect(
            existing_work.get_absolute_url()
        )

    details = None
    import_error = ""

    try:
        details = fetch_tmdb_details(
            media_type=media_type,
            tmdb_id=tmdb_id,
        )
    except (
        TMDBClientError,
        TMDBImportError,
    ) as error:
        import_error = str(error)

    if request.method == "POST":
        form = TMDBImportForm(
            request.POST,
            suggested_presentation=(
                details.get("presentation")
                if details
                else None
            ),
        )

        if (
            details is not None
            and form.is_valid()
        ):
            try:
                work = import_tmdb_work(
                    details=details,
                    status=(
                        form.cleaned_data[
                            "status"
                        ]
                    ),
                    notes=(
                        form.cleaned_data[
                            "notes"
                        ]
                    ),
                    presentation=(
                        form.cleaned_data[
                            "presentation"
                        ]
                    ),
                )
            except TMDBDuplicateWorkError as error:
                return redirect(
                    error.existing_work
                    .get_absolute_url()
                )
            except TMDBImportError as error:
                import_error = str(error)
            else:
                return redirect(
                    work.get_absolute_url()
                )
    else:
        form = TMDBImportForm(
            suggested_presentation=(
                details.get("presentation")
                if details
                else None
            ),
        )

    return render(
        request,
        "watchroom/tmdb_import.html",
        {
            "active_page": "tmdb_search",
            "details": details,
            "form": form,
            "import_error": import_error,
            "media_type": media_type,
            "tmdb_id": tmdb_id,
        },
    )


@login_required
@require_POST
def refresh_tmdb_work(
    request,
    slug,
):
    work = get_object_or_404(
        MediaWork,
        slug=slug,
    )

    if work.tmdb_id is None:
        messages.error(
            request,
            (
                "This work is not linked "
                "to TMDB."
            ),
        )

        return redirect(
            work.get_absolute_url()
        )

    try:
        result = refresh_work_from_tmdb(
            work=work
        )
    except (
        TMDBClientError,
        TMDBImportError,
        TMDBRefreshError,
    ) as error:
        messages.error(
            request,
            (
                "TMDB refresh failed: "
                f"{error}"
            ),
        )

        return redirect(
            work.get_absolute_url()
        )

    messages.success(
        request,
        (
            "TMDB refresh complete. "
            f"{result.created_seasons} "
            "season(s) added and "
            f"{result.updated_seasons} "
            "season(s) updated."
        ),
    )

    if result.preserved_runtime:
        messages.warning(
            request,
            (
                "The local runtime was preserved "
                "because TMDB returned a value "
                "lower than existing progress."
            ),
        )

    if (
        result.preserved_episode_totals
        > 0
    ):
        messages.warning(
            request,
            (
                f"{result.preserved_episode_totals} "
                "season total(s) were preserved "
                "because TMDB returned episode "
                "counts lower than existing "
                "progress."
            ),
        )

    return redirect(
        result.work.get_absolute_url()
    )


