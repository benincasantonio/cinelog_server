from fastapi import APIRouter, Depends, Request, HTTPException

from app.dependencies.auth_dependency import auth_dependency
from app.utils.access_token_utils import get_user_id_from_token
from app.services.stats_service import StatsService
from app.schemas.stats_schemas import StatsResponse, StatsRequest
from app.utils.exceptions import AppException

router = APIRouter()

stats_service = StatsService()


@router.get("/me", response_model=StatsResponse)
def get_my_stats(
    request: Request,
    stats_request: StatsRequest = Depends(),
    _: bool = Depends(auth_dependency),
) -> StatsResponse:
    """
    Get stats for the logged in user.

    Requires authentication via Bearer token.
    """
    token = request.headers.get("Authorization")
    try:
        user_id = get_user_id_from_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Validate year bounds if both provided
    if (
        stats_request.year_from is not None
        and stats_request.year_to is not None
        and stats_request.year_from > stats_request.year_to
    ):
        raise HTTPException(
            status_code=400, detail="yearFrom cannot be greater than yearTo"
        )

    try:
        return stats_service.get_user_stats(
            user_id=user_id,
            year_from=stats_request.year_from,
            year_to=stats_request.year_to,
        )
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Stats endpoint not implemented yet"
        )
    except AppException as e:
        raise e
