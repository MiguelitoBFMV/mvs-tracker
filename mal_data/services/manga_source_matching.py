import unicodedata

from difflib import SequenceMatcher


def normalize_source_title(value):
    normalized = unicodedata.normalize(
        "NFKC",
        value or "",
    ).casefold()

    normalized = "".join(
        character
        if character.isalnum()
        else " "
        for character in normalized
    )

    return " ".join(
        normalized.split()
    )


def source_title_score(
    reference_title,
    candidate_title,
):
    reference = normalize_source_title(
        reference_title
    )
    candidate = normalize_source_title(
        candidate_title
    )

    if not reference or not candidate:
        return 0.0

    if reference == candidate:
        return 100.0

    if (
        reference in candidate
        or candidate in reference
    ):
        return 92.0

    return round(
        SequenceMatcher(
            None,
            reference,
            candidate,
        ).ratio()
        * 100,
        2,
    )

