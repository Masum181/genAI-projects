"""Jinja-rendered browser pages for common user workflows."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Principal, get_current_principal, get_db
from app.core.config import settings
from app.services import auth_service, conversation_service, document_service

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
router = APIRouter(tags=["browser"])


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request) -> Response:
    if request.cookies.et("access_token"):
        return RedirectResponse("/ui/", status_code=303)
    return RedirectResponse("/login", status_code=303)


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request, "error": None},
    )


@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
async def browser_login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
    organization_slug: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    identity = await auth_service.authenticate_browser(
        db, email, password, organization_slug
    )
    if identity is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "error": "Invalid email, password, or organization.",
            },
            status_code=401,
        )
    user, organization = identity
    token = auth_service.token_data(user, organization.id)["access_token"]
    result = RedirectResponse("/ui/", status_code=303)
    result.set_cookie(
        "access_token",
        token,
        max_age=settings.app.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.app.environment == "production",
        samesite="strict",
        path="/",
    )
    return result


@router.get("/ui/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> Response:
    document_count = await document_service.dashboard_document_count(db, principal)
    conversation_count = await conversation_service.dashboard_conversation_count(
        db, principal
    )
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "principal": principal,
            "document_count": document_count or 0,
            "conversation_count": conversation_count or 0,
        },
    )


@router.get("/ui/documents", response_class=HTMLResponse, include_in_schema=False)
async def browse_documents(
    request: Request,
    page: int = 1,
    page_size: int = 25,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> Response:
    documents = await document_service.list_browser_documents(
        db, principal, page, page_size
    )
    return templates.TemplateResponse(
        request=request,
        name="documents.html",
        context={"request": request, "principal": principal, "documents": documents},
    )


@router.get("/ui/conversations", response_class=HTMLResponse, include_in_schema=False)
async def browse_conversations(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> Response:
    conversations = await conversation_service.recent_conversations(db, principal)
    return templates.TemplateResponse(
        request=request,
        name="conversations.html",
        context={
            "request": request,
            "principal": principal,
            "conversations": conversations,
        },
    )


@router.post("/ui/logout", include_in_schema=False)
async def browser_logout(request: Request) -> Response:
    token = request.cookies.get("access_token")
    if token:
        revoked = await auth_service.revoke_browser_access_token(
            request.app.state.redis, token
        )
        if not revoked:
            logger.info("Browser logout received an invalid access token")
    result = RedirectResponse("/login", status_code=303)
    result.delete_cookie("access_token", path="/", httponly=True, samesite="strict")
    return result
