import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account


async def test_account_requires_exactly_one_owner(db_session: AsyncSession) -> None:
    db_session.add(
        Account(
            account_number="ACC-INVALID-OWNER",
            owner_user_id=None,
            owner_merchant_id=None,
            currency="INR",
            status="active",
            available_balance_minor=0,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
