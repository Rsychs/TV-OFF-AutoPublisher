"""Pure planning helpers for TV OFF long-form section generation."""
import math

SECTION_SECONDS = 204
CROSSFADE_SECONDS = 2.0
TARGET_HOURS = (1, 3, 8, 10)


def required_sections(hours: int) -> int:
    if hours not in TARGET_HOURS:
        raise ValueError(f"Unsupported target duration: {hours}h")
    # Conservative count: every section contributes at least one section minus
    # one crossfade, so there is always enough source to trim to the exact target.
    return math.ceil((hours * 3600) / (SECTION_SECONDS - CROSSFADE_SECONDS))


def unique_title(genre: str, used: set[str], ordinal: int, title_options: dict[str, list[str]]) -> str:
    options = title_options[genre]
    for offset in range(len(options)):
        candidate = options[(ordinal + offset) % len(options)]
        if candidate not in used:
            used.add(candidate)
            return candidate
    # Section titles are provenance labels, not the public video title.
    # Keep them distinct even for 10-hour sessions with many sections per genre.
    base = options[ordinal % len(options)]
    candidate = f"{base} — Section {ordinal + 1}"
    while candidate in used:
        ordinal += 1
        candidate = f"{base} — Section {ordinal + 1}"
    used.add(candidate)
    return candidate
