"""Feedback submission endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Principal, get_current_principal, get_db
from app.api.v1.common import response
from app.schemas.requests import FeedbackCreate
from app.services import feedback_service

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: FeedbackCreate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await feedback_service.submit_feedback(
        session=db, principal=principal, body=body
    )
    return response(request, data)


@router.get("/{feedback_id}")
async def get_feedback(
    feedback_id: UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await feedback_service.get_feedback(db, principal, feedback_id)
    return response(request, data)
