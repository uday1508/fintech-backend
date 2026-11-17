from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.common.envelopes import success_payload
from app.core.permissions import require_permission
from app.db.session import get_db_session
from app.merchants.models import MerchantMembership
from app.users.models import Permission, RolePermission, User

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
async def list_accounts(
    request: Request,
    user: User = Depends(require_permission("account.read_own")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    merchant_ids = (
        select(MerchantMembership.merchant_id)
        .join(RolePermission, RolePermission.role_id == MerchantMembership.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            MerchantMembership.user_id == user.id,
            MerchantMembership.status == "active",
            Permission.code == "merchant.account.read",
        )
    )
    accounts = await session.scalars(
        select(Account)
        .where(
            or_(
                Account.owner_user_id == user.id,
                Account.owner_merchant_id.in_(merchant_ids),
            )
        )
        .order_by(Account.created_at, Account.id)
    )
    data = []
    for account in accounts:
        owner_id = account.owner_user_id or account.owner_merchant_id
        data.append(
            {
                "id": str(account.id),
                "account_number": account.account_number,
                "owner_type": "user" if account.owner_user_id else "merchant",
                "owner_id": str(owner_id),
                "currency": account.currency,
                "status": account.status,
                "available_balance_minor": account.available_balance_minor,
            }
        )
    return success_payload(data, request.state.request_id)
