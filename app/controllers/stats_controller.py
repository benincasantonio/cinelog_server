from fastapi import APIRouter, Depends, Request, HTTPException

from app.dependencies.auth_dependency import auth_dependency
from app.services.stats_service import StatsService
from app.schemas.stats_schemas import StatsResponse, StatsRequest
from app.utils.exceptions import AppException

router = APIRouter()

stats_service = StatsService()


@router.get("/me", response_model=StatsResponse)
def get_my_stats(
    request: Request,
    stats_request: StatsRequest = Depends(),
    user_id: str = Depends(auth_dependency),
) -> StatsResponse:
    """
    Get stats for the logged in user.

    Requires authentication via Bearer token.
    """
    
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
