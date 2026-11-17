from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.service import create_wallet_account
from app.common.envelopes import success_payload
from app.common.enums import RoleCode
from app.core.permissions import require_permission
from app.db.session import get_db_session
from app.merchants.models import Merchant, MerchantCategory, MerchantMembership
from app.merchants.schemas import MerchantCreateRequest
from app.users.models import Role, User, UserRole

router = APIRouter(tags=["merchants"])


@router.get("/merchant-categories")
async def list_categories(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    categories = await session.scalars(
        select(MerchantCategory)
        .where(MerchantCategory.is_active.is_(True))
        .order_by(MerchantCategory.name, MerchantCategory.id)
    )
    return success_payload(
        [
            {"id": str(category.id), "code": category.code, "name": category.name}
            for category in categories
        ],
        request.state.request_id,
    )


@router.post("/merchants", status_code=status.HTTP_201_CREATED)
async def create_merchant(
    payload: MerchantCreateRequest,
    request: Request,
    user: User = Depends(require_permission("merchant.create")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    category = await session.get(MerchantCategory, payload.category_id)
    if category is None or not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_CATEGORY", "message": "An active merchant category is required."},
        )

    if await session.scalar(
        select(Merchant.id).where(Merchant.username == payload.username)
    ) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MERCHANT_USERNAME_TAKEN", "message": "This business username is already in use."},
        )

    owner_role = await session.scalar(
        select(Role).where(Role.code == RoleCode.MERCHANT_OWNER.value)
    )
    if owner_role is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "IDENTITY_NOT_INITIALIZED", "message": "Seed roles before creating merchants."},
        )

    merchant = Merchant(
        name=payload.name,
        username=payload.username,
        category_id=category.id,
        status="active",
    )
    session.add(merchant)
    await session.flush()
    membership = MerchantMembership(
        merchant_id=merchant.id,
        user_id=user.id,
        role_id=owner_role.id,
        status="active",
    )
    session.add(membership)
    if await session.get(UserRole, (user.id, owner_role.id)) is None:
        session.add(UserRole(user_id=user.id, role_id=owner_role.id))
    account = await create_wallet_account(session, merchant_id=merchant.id)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        constraint = getattr(exc.orig, "constraint_name", None) or getattr(
            getattr(exc.orig, "diag", None), "constraint_name", None
        )
        if constraint != "ix_merchants_username":
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MERCHANT_USERNAME_TAKEN", "message": "This business username is already in use."},
        ) from exc

    return success_payload(
        {
            "id": str(merchant.id),
            "name": merchant.name,
            "username": merchant.username,
            "category_id": str(merchant.category_id),
            "status": merchant.status,
            "wallet_account_id": str(account.id),
        },
        request.state.request_id,
    )
