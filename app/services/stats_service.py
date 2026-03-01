from datetime import date

from app.repository.log_repository import LogRepository
from app.schemas.log_schemas import LogListRequest


class StatsService:
    def __init__(self, log_repository: LogRepository | None = None):
        self.log_repository = log_repository or LogRepository()

    async def get_user_stats(
        self, user_id: str, year_from: int | None = None, year_to: int | None = None
    ) -> dict:
        """
        Retrieve summary stats for a given user.

        Returns a dictionary matching the `StatsResponse` schema. For now this
        implements only the `summary` section; `distribution` and `pace` are
        returned with zeroed/default values.
        """
        date_from: date | None = (
            date(year_from, 1, 1) if year_from is not None else None
        )
        date_to: date | None = date(year_to, 12, 31) if year_to is not None else None

        request: LogListRequest | None = None
        if date_from is not None or date_to is not None:
            request = LogListRequest(
                sort_by="dateWatched",
                sort_order="desc",
                watched_where=None,
                date_watched_from=date_from,
                date_watched_to=date_to,
            )

        logs = await self.log_repository.find_logs_by_user_id(user_id, request=request)

        summary = self.compute_summary(logs)

        distribution = self.compute_distribution(logs)

        pace = {"on_track_for": 0, "current_average": 0.0, "days_since_last_log": 0}

        return {"summary": summary, "distribution": distribution, "pace": pace}

    def compute_summary(self, logs: list) -> dict:
        """
        Compute the summary stats from a list of log records.

        Args:
            logs: list of log dicts or objects returned by the repository

        Returns:
            dict with keys: total_watches, unique_titles, total_rewatches, total_minutes
        """
        if not logs:
            return {
                "total_watches": 0,
                "unique_titles": 0,
                "total_rewatches": 0,
                "total_minutes": 0,
                "vote_average": None,
            }

        total_watches = len(logs)

        # unique titles are unique movieId values
        unique_titles = len({str(log.get("movieId")) for log in logs}) if logs else 0

        total_rewatches = max(0, total_watches - unique_titles)

        votes_sum: float = 0
        movie_with_votes_count: int = 0

        total_minutes = 0
        for log in logs:
            movie = log.get("movie") if isinstance(log, dict) else None
            movie_rating: int | None = (
                log.get("movieRating") if isinstance(log, dict) else None
            )
            runtime = 0
            if movie:
                runtime = getattr(movie, "runtime", 0) or 0
            else:
                runtime = log.get("runtime", 0) if isinstance(log, dict) else 0

            if movie_rating:
                try:
                    votes_sum += float(movie_rating)
                    movie_with_votes_count += 1
                except (TypeError, ValueError):
                    pass

            try:
                total_minutes += int(runtime)
            except (TypeError, ValueError):
                # ignore invalid runtime values
                pass

        return {
            "total_watches": total_watches,
            "unique_titles": unique_titles,
            "total_rewatches": total_rewatches,
            "total_minutes": total_minutes,
            "vote_average": (
                votes_sum / movie_with_votes_count
                if movie_with_votes_count > 0
                else None
            ),
        }

    def compute_distribution(self, logs: list) -> dict:
        """
        Compute the distribution stats from a list of log records.

        Args:
            logs: list of log dicts or objects returned by the repository

        Returns:
            dict with keys: by_method (cinema, streaming, home_video, tv, other

        """

        distribution = {
            "by_method": {
                "cinema": 0,
                "streaming": 0,
                "home_video": 0,
                "tv": 0,
                "other": 0,
            }
        }

        for log in logs:
            watched_where = None
            if isinstance(log, dict):
                watched_where = log.get("watchedWhere")
            else:
                watched_where = getattr(log, "watched_where", None)

            if watched_where == "cinema":
                distribution["by_method"]["cinema"] += 1
            elif watched_where == "streaming":
                distribution["by_method"]["streaming"] += 1
            elif watched_where == "homeVideo":
                distribution["by_method"]["home_video"] += 1
            elif watched_where == "tv":
                distribution["by_method"]["tv"] += 1
            elif watched_where == "other":
                distribution["by_method"]["other"] += 1

        return distribution
