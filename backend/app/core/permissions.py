import uuid
from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db_session
from app.merchants.models import MerchantMembership
from app.users.models import Permission, RolePermission, User, UserRole

_bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "Valid authentication is required."},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise _unauthorized()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "type"]},
        )
        if claims["type"] != "access" or not isinstance(claims["sub"], str):
            raise _unauthorized()
        user_id = uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
        raise _unauthorized() from exc

    user = await session.get(User, user_id)
    if user is None or user.status != "active":
        raise _unauthorized()
    return user


def require_permission(permission_code: str) -> Callable[..., Any]:
    async def dependency(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        permission = await session.scalar(
            select(Permission.code)
            .select_from(UserRole)
            .join(RolePermission, RolePermission.role_id == UserRole.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(UserRole.user_id == user.id, Permission.code == permission_code)
            .limit(1)
        )
        if permission is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "You do not have this permission."},
            )
        return user

    return dependency


def require_merchant_permission(permission_code: str) -> Callable[..., Any]:
    async def dependency(
        merchant_id: uuid.UUID,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> MerchantMembership:
        membership = await session.scalar(
            select(MerchantMembership)
            .join(RolePermission, RolePermission.role_id == MerchantMembership.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                MerchantMembership.merchant_id == merchant_id,
                MerchantMembership.user_id == user.id,
                MerchantMembership.status == "active",
                Permission.code == permission_code,
            )
            .limit(1)
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": "An active merchant membership with this permission is required.",
                },
            )
        return membership

    return dependency