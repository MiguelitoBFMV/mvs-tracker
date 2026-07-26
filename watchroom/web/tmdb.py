from django.contrib.auth.decorators import (
    login_required,
)
from django.shortcuts import render

from watchroom.forms import (
    TMDBSearchForm,
)
from watchroom.models import MediaWork
from watchroom.services.tmdb_client import (
    TMDBClient,
    TMDBClientError,
)
from watchroom.services.tmdb_normalizer import (
    TMDBNormalizationError,
    normalize_movie_search_result,
    normalize_series_search_result,
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

