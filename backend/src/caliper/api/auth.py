from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from caliper.adapters.postgres.auth_repository import (
    admin_is_configured,
    authenticate,
    revoke_session,
    valid_session,
)
from caliper.adapters.postgres.database import get_session

router = APIRouter(prefix="/api/auth", tags=["authentication"])
COOKIE_NAME = "caliper_admin_session"


class LoginInput(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


async def require_admin(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> None:
    if not await valid_session(session, request.cookies.get(COOKIE_NAME)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )


@router.get("/session")
async def session_status(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict[str, bool]:
    return {
        "configured": await admin_is_configured(session),
        "authenticated": await valid_session(session, request.cookies.get(COOKIE_NAME)),
    }


@router.post("/session")
async def login(
    payload: LoginInput,
    response: Response,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    if not await admin_is_configured(session):
        raise HTTPException(status_code=409, detail="Administrator setup is required")
    if request.headers.get("origin") and request.headers["origin"] != str(request.base_url).rstrip(
        "/"
    ):
        raise HTTPException(status_code=403, detail="Request origin rejected")
    token = await authenticate(session, payload.password)
    if token is None:
        raise HTTPException(status_code=401, detail="Incorrect password")
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=43200,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return {"authenticated": True}


@router.delete("/session")
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="Request origin rejected")
    await revoke_session(session, request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")
    return response
