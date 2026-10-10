"""Production provider composition; tests replace this factory with a fake."""

from app.providers.movie_provider_protocol import MovieProviderProtocol
from app.providers.tmdb import TMDBMovieProvider


def get_movie_provider() -> MovieProviderProtocol:
    return TMDBMovieProvider.get_instance()
