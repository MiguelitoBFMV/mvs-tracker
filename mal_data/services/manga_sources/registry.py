from mal_data.services.manga_sources.weeb_central import (
    WeebCentralClient,
)
from mal_data.services.manga_sources.manga_plus import (
    MangaPlusClient,
)


PROVIDER_CLIENTS = {
    "manga_plus": MangaPlusClient,
    "weeb_central": WeebCentralClient,
}

PROVIDER_LABELS = {
    "manga_plus": "MANGA Plus",
    "weeb_central": "Weeb Central",
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
    client_class = PROVIDER_CLIENTS.get(
        provider
    )

    if client_class is None:
        raise ValueError(
            (
                "Unsupported manga source "
                f"provider: {provider}"
            )
        )

    return client_class()