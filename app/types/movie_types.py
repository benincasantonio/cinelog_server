"""Movie-domain enum types.

Types:
    MovieProviderName — enabled source identifiers accepted by movie persistence
"""

from enum import StrEnum


class MovieProviderName(StrEnum):
    """Enabled movie providers; additions also require a schema migration."""

    TMDB = "tmdb"
