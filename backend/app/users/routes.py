from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserRead
from app.common.envelopes import success_payload
from app.common.enums import RoleCode, WorkspaceType
from app.core.permissions import get_current_user
from app.db.session import get_db_session
from app.merchants.models import Merchant, MerchantMembership
from app.users.models import Role, User, UserRole

router = APIRouter(prefix="/me", tags=["workspaces"])


@router.get("")
async def me(
    request: Request,
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    return success_payload(
        UserRead.model_validate(user).model_dump(mode="json"),
        request.state.request_id,
    )


@router.get("/workspaces")
async def list_workspaces(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    user_roles = await session.scalars(
        select(Role.code)
        .select_from(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user.id)
    )
    role_codes = set(user_roles)
    workspaces: list[dict[str, object]] = []
    if RoleCode.CUSTOMER.value in role_codes:
        workspaces.append(
            {
                "type": WorkspaceType.CUSTOMER.value,
                "id": str(user.id),
                "name": user.full_name,
            }
        )

    memberships = await session.execute(
        select(MerchantMembership, Merchant, Role)
        .join(Merchant, Merchant.id == MerchantMembership.merchant_id)
        .join(Role, Role.id == MerchantMembership.role_id)
        .where(
            MerchantMembership.user_id == user.id,
            MerchantMembership.status == "active",
            Merchant.status == "active",
        )
        .order_by(Merchant.name, Merchant.id)
    )
    for membership, merchant, role in memberships:
        workspaces.append(
            {
                "type": WorkspaceType.MERCHANT.value,
                "id": str(merchant.id),
                "name": merchant.name,
                "username": merchant.username,
                "membership_id": str(membership.id),
                "role": role.code,
            }
        )

    return success_payload(workspaces, request.state.request_id)
