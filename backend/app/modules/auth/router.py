from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.auth.dependencies import current_claims
from app.modules.auth.schemas import LoginRequest, LoginResponse, SessionUser
from app.modules.auth.service import authenticate, issue_token, user_claims

router = APIRouter(prefix="/auth", tags=["auth"])


def database_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[Session, Depends(database_session)],
) -> LoginResponse:
    user = authenticate(session, payload.email, payload.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    roles, permissions = user_claims(user)
    token = issue_token(user)

    response.set_cookie(
        key="nab_v2_session",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=43200,
    )

    return LoginResponse(
        token=token,
        user=SessionUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            roles=roles,
            permissions=permissions,
            is_superuser=user.is_superuser,
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key="nab_v2_session",
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return response


