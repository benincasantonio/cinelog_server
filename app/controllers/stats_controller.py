from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_stats_service
from app.schemas.stats_schemas import StatsRequest, StatsResponse
from app.services.stats_service import StatsService
from app.utils.exceptions_utils import AppException

router = APIRouter()


@router.get("/me", response_model=StatsResponse)
async def get_my_stats(
    request: Request,
    stats_request: StatsRequest = Depends(),
    user_id: PydanticObjectId = Depends(auth_dependency),
    stats_service: StatsService = Depends(get_stats_service),
) -> StatsResponse:
    """
    Get stats for the logged in user.

    Requires authentication via Cookie token.
    """

    # Validate year bounds if both provided
    if (
        stats_request.year_from is not None
        and stats_request.year_to is not None
        and stats_request.year_from > stats_request.year_to
    ):
        raise HTTPException(status_code=400, detail="yearFrom cannot be greater than yearTo")

    try:
        stats_response = await stats_service.get_user_stats(
            user_id=user_id,
            year_from=stats_request.year_from,
            year_to=stats_request.year_to,
        )
        return stats_response
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Stats endpoint not implemented yet") from None
    except AppException as e:
        raise e
