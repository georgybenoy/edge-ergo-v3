"""EdgeErgo V3 — Dashboard User Auth Endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AuthUser, get_current_user
from app.schemas.api_models import UserMeResponse

router = APIRouter(tags=["Authentication"])


@router.get("/me", response_model=UserMeResponse)
async def get_me(current_user: AuthUser = Depends(get_current_user)) -> UserMeResponse:
    """Returns the authenticated user's identity, active organization, and assigned role."""
    return UserMeResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        organization_id=current_user.organization_id,
        organization_slug=current_user.organization_slug,
        role=current_user.role,
    )
