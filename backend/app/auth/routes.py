from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.service import create_wallet_account
from app.auth.models import RefreshSession
from app.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UserRead,
)
from app.auth.tokens import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    refresh_expiration,
)
from app.common.envelopes import success_payload
from app.common.enums import RoleCode
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.session import get_db_session
from app.users.models import Role, User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_error(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"code": code, "message": message},
    )


async def _issue_tokens(
    session: AsyncSession,
    user: User,
) -> tuple[dict[str, object], RefreshSession]:
    refresh_token = create_refresh_token()
    refresh_session = RefreshSession(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=refresh_expiration(),
    )
    session.add(refresh_session)
    await session.flush()
    return (
        {
            "access_token": create_access_token(user.id),
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        },
        refresh_session,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    customer_role = await session.scalar(
        select(Role).where(Role.code == RoleCode.CUSTOMER.value)
    )
    if customer_role is None:
        raise _auth_error(
            "IDENTITY_NOT_INITIALIZED",
            "Run the role and permission seed script before registering users.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if await session.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise _auth_error(
            "EMAIL_ALREADY_REGISTERED",
            "An account with this email already exists.",
            status.HTTP_409_CONFLICT,
        )
    if await session.scalar(select(User.id).where(User.username == payload.username)) is not None:
        raise _auth_error(
            "USERNAME_ALREADY_TAKEN",
            "This username is already in use.",
            status.HTTP_409_CONFLICT,
        )

    user = User(
        full_name=payload.full_name,
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        status="active",
    )
    session.add(user)
    try:
        await session.flush()
        session.add(UserRole(user_id=user.id, role_id=customer_role.id))
        account = await create_wallet_account(session, user_id=user.id)
        tokens, _ = await _issue_tokens(session, user)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        constraint = getattr(exc.orig, "constraint_name", None) or getattr(
            getattr(exc.orig, "diag", None),
            "constraint_name",
            None,
        )
        if constraint == "ix_users_username":
            raise _auth_error(
                "USERNAME_ALREADY_TAKEN",
                "This username is already in use.",
                status.HTTP_409_CONFLICT,
            ) from exc
        if constraint != "ix_users_email":
            raise
        raise _auth_error(
            "EMAIL_ALREADY_REGISTERED",
            "An account with this email already exists.",
            status.HTTP_409_CONFLICT,
        ) from exc

    return success_payload(
        {
            "user": UserRead.model_validate(user).model_dump(mode="json"),
            "wallet_account_id": str(account.id),
            **tokens,
        },
        request.state.request_id,
    )


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    login_field = User.email if payload.email is not None else User.username
    login_value = payload.email if payload.email is not None else payload.username
    user = await session.scalar(select(User).where(login_field == login_value))
    if (
        user is None
        or user.status != "active"
        or not verify_password(payload.password, user.password_hash)
    ):
        raise _auth_error(
            "INVALID_CREDENTIALS",
            "Email/username or password is incorrect.",
            status.HTTP_401_UNAUTHORIZED,
        )

    tokens, _ = await _issue_tokens(session, user)
    await session.commit()
    return success_payload(tokens, request.state.request_id)


@router.post("/refresh")
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    now = datetime.now(UTC)
    old_session = await session.scalar(
        select(RefreshSession)
        .where(RefreshSession.token_hash == hash_refresh_token(payload.refresh_token))
        .with_for_update()
    )
    if (
        old_session is None
        or old_session.revoked_at is not None
        or old_session.expires_at <= now
    ):
        raise _auth_error(
            "INVALID_REFRESH_TOKEN",
            "The refresh token is invalid or expired.",
            status.HTTP_401_UNAUTHORIZED,
        )

    user = await session.get(User, old_session.user_id)
    if user is None or user.status != "active":
        raise _auth_error(
            "INVALID_REFRESH_TOKEN",
            "The refresh token is invalid or expired.",
            status.HTTP_401_UNAUTHORIZED,
        )

    old_session.revoked_at = now
    tokens, replacement = await _issue_tokens(session, user)
    old_session.replaced_by_id = replacement.id
    await session.commit()
    return success_payload(tokens, request.state.request_id)


@router.post("/logout")
async def logout(
    payload: LogoutRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    refresh_session = await session.scalar(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(payload.refresh_token)
        )
    )
    if refresh_session is not None and refresh_session.revoked_at is None:
        refresh_session.revoked_at = datetime.now(UTC)
        await session.commit()
    return success_payload({"logged_out": True}, request.state.request_id)


