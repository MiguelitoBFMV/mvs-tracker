from mal_data.services.manga_sources.manga_fire import (
    MangaFireClient,
)
from mal_data.services.manga_sources.manga_plus import (
    MangaPlusClient,
)
from mal_data.services.manga_sources.weeb_central import (
    WeebCentralClient,
)
from mal_data.services.manga_sources.mangas_in import (
    MangasInClient,
)
from mal_data.services.manga_sources.mangabat import (
    MangabatClient,
)

PROVIDER_CLIENTS = {
    "manga_plus": MangaPlusClient,
    "weeb_central": WeebCentralClient,
    "manga_fire": MangaFireClient,
    "mangas_in": MangasInClient,
    "mangabat": MangabatClient,
}

PROVIDER_LABELS = {
    "manga_plus": "MANGA Plus",
    "weeb_central": "Weeb Central",
    "manga_fire": "MangaFire",
    "mangas_in": "Mangas.in",
    "mangabat": "Mangabat",
}

OFFICIAL_PROVIDERS = {
    "manga_plus",
}


def is_official_provider(provider):
    return provider in OFFICIAL_PROVIDERS


def get_provider_label(provider):
    return PROVIDER_LABELS.get(
        provider,
        provider.replace(
            "_",
            " ",
        ).title(),
    )


def build_provider_client(provider):
    client_class = (
        PROVIDER_CLIENTS.get(
            provider
        )
    )

    if client_class is None:
        raise ValueError(
            (
                "Unsupported manga source "
                f"provider: {provider}"
            )
        )

    return client_class()
