import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.enums import RoleCode
from app.db.session import engine
from app.merchants.models import MerchantCategory
from app.users.models import Permission, Role, RolePermission


MERCHANT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("food-beverage", "Food and Beverage"),
    ("automotive", "Automotive"),
    ("transport", "Transport"),
    ("retail", "Retail"),
    ("healthcare", "Healthcare"),
)

PERMISSIONS: dict[str, str] = {
    "account.read_own": "Read accounts owned by the authenticated user.",
    "payment.create": "Create a payment from an owned account.",
    "payment.read_own": "Read payments made by the authenticated user.",
    "merchant.create": "Create a merchant workspace.",
    "merchant.account.read": "Read accounts owned by an authorized merchant.",
    "merchant.payment.read": "Read payments for an authorized merchant.",
    "merchant.refund.create": "Request refunds for an authorized merchant.",
    "merchant.analytics.read": "Read analytics for an authorized merchant.",
    "merchant.reconciliation.manage": "Manage merchant reconciliation.",
    "merchant.members.manage": "Manage merchant memberships.",
    "fraud.alert.review": "Review fraud alerts.",
}

ROLE_PERMISSION_CODES: dict[RoleCode, set[str]] = {
    RoleCode.CUSTOMER: {
        "account.read_own",
        "payment.create",
        "payment.read_own",
        "merchant.create",
    },
    RoleCode.MERCHANT_OWNER: {
        "merchant.account.read",
        "merchant.payment.read",
        "merchant.refund.create",
        "merchant.analytics.read",
        "merchant.reconciliation.manage",
        "merchant.members.manage",
    },
    RoleCode.MERCHANT_CASHIER: {
        "merchant.payment.read",
        "merchant.refund.create",
    },
    RoleCode.MERCHANT_ANALYST: {
        "merchant.payment.read",
        "merchant.analytics.read",
    },
    RoleCode.PLATFORM_ADMIN: set(PERMISSIONS),
}


async def seed_identity(session: AsyncSession) -> None:
    roles: dict[str, Role] = {}
    for role_code in RoleCode:
        role = await session.scalar(select(Role).where(Role.code == role_code.value))
        if role is None:
            role = Role(code=role_code.value, name=role_code.value.replace("_", " ").title())
            session.add(role)
        roles[role_code.value] = role

    permissions: dict[str, Permission] = {}
    for code, description in PERMISSIONS.items():
        permission = await session.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, description=description)
            session.add(permission)
        permissions[code] = permission

    await session.flush()

    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role = roles[role_code.value]
        for permission_code in permission_codes:
            permission = permissions[permission_code]
            link = await session.get(RolePermission, (role.id, permission.id))
            if link is None:
                session.add(RolePermission(role_id=role.id, permission_id=permission.id))
    await session.flush()


async def seed_categories(session: AsyncSession) -> None:
    for code, name in MERCHANT_CATEGORIES:
        category = await session.scalar(
            select(MerchantCategory).where(MerchantCategory.code == code)
        )
        if category is None:
            session.add(MerchantCategory(code=code, name=name, is_active=True))
    await session.flush()


async def main() -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory.begin() as session:
        await seed_identity(session)
        await seed_categories(session)


if __name__ == "__main__":
    asyncio.run(main())
