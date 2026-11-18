"""Composition root for version 1 API routes."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.departments import router as departments_router
from app.api.v1.documents import router as documents_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.users import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(organizations_router)
router.include_router(users_router)
router.include_router(departments_router)
router.include_router(documents_router)
router.include_router(ingestion_router)
router.include_router(chat_router)
router.include_router(conversations_router)
router.include_router(feedback_router)
router.include_router(analytics_router)
router.include_router(admin_router)
