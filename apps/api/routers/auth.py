from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from apps.api.config import limiter
from apps.api.schemas.auth import AuthSessionResponse, DemoSessionResponse, LoginRequest, RegisterRequest
from apps.api.services.auth_service import AuthService
from apps.api.services.demo_service import create_demo_session

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/login", response_model=AuthSessionResponse)
@limiter.limit("10/minute")
def login(request: Request, response: Response, payload: LoginRequest) -> dict[str, object]:
    return AuthService().login(payload.identifier, payload.password)


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def register(request: Request, response: Response, payload: RegisterRequest) -> dict[str, object]:
    profile = AuthService().register(
        username=payload.username,
        email=str(payload.email),
        password=payload.password,
    )
    return {
        "user_uuid": profile["user_uuid"],
        "username": profile["username"],
        "account_status": profile["account_status"],
        "detail": "Registration completed. Your account is pending activation.",
    }


@router.post("/demo-session", response_model=DemoSessionResponse)
@limiter.limit("20/hour")
def demo_session(request: Request, response: Response) -> dict[str, str]:
    token, expires_at = create_demo_session()
    return {"demo_token": token, "expires_at": expires_at.isoformat()}
