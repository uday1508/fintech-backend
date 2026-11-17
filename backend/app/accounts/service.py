import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account


def new_wallet_account(
    *,
    user_id: uuid.UUID | None = None,
    merchant_id: uuid.UUID | None = None,
    currency: str = "INR",
) -> Account:
    if (user_id is None) == (merchant_id is None):
        raise ValueError("Exactly one of user_id or merchant_id must be provided")
    return Account(
        account_number=f"ACC-{uuid.uuid4().hex.upper()}",
        owner_user_id=user_id,
        owner_merchant_id=merchant_id,
        currency=currency,
        status="active",
        available_balance_minor=0,
    )


async def create_wallet_account(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    merchant_id: uuid.UUID | None = None,
    currency: str = "INR",
) -> Account:
    account = new_wallet_account(user_id=user_id, merchant_id=merchant_id, currency=currency)
    session.add(account)
    await session.flush()
    return account
