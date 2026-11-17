import uuid

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_merchant_permission
from app.users.models import User


async def test_merchant_creation_creates_membership_and_wallet(
    client: AsyncClient,
) -> None:
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Merchant Owner",
            "username": "owner_person",
            "email": "owner@example.com",
            "password": "correct-horse-battery",
        },
    )
    token = registration.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    categories = await client.get("/api/v1/merchant-categories")
    assert categories.status_code == 200
    category_id = categories.json()["data"][0]["id"]

    created = await client.post(
        "/api/v1/merchants",
        headers=headers,
        json={"name": "Corner Cafe", "username": "corner_cafe", "category_id": category_id},
    )
    assert created.status_code == 201
    merchant = created.json()["data"]
    assert merchant["wallet_account_id"]
    assert merchant["username"] == "corner_cafe"

    workspaces = await client.get("/api/v1/me/workspaces", headers=headers)
    assert workspaces.status_code == 200
    assert [workspace["type"] for workspace in workspaces.json()["data"]] == [
        "customer",
        "merchant",
    ]
    assert workspaces.json()["data"][1]["username"] == "corner_cafe"

    accounts = await client.get("/api/v1/accounts", headers=headers)
    assert accounts.status_code == 200
    assert len(accounts.json()["data"]) == 2
    assert {account["owner_type"] for account in accounts.json()["data"]} == {
        "user",
        "merchant",
    }

    duplicate = await client.post(
        "/api/v1/merchants",
        headers=headers,
        json={"name": "Duplicate Cafe", "username": "CORNER_CAFE", "category_id": category_id},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "MERCHANT_USERNAME_TAKEN"


async def test_account_list_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/accounts")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_merchant_permission_requires_active_membership(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_registration = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Merchant Owner",
            "username": "guard_owner",
            "email": "guard-owner@example.com",
            "password": "correct-horse-battery",
        },
    )
    owner_token = owner_registration.json()["data"]["access_token"]
    categories = await client.get("/api/v1/merchant-categories")
    merchant_response = await client.post(
        "/api/v1/merchants",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "Guarded Shop",
            "username": "guarded_shop",
            "category_id": categories.json()["data"][0]["id"],
        },
    )
    merchant_id = uuid.UUID(merchant_response.json()["data"]["id"])

    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Unrelated Customer",
            "username": "other_customer",
            "email": "guard-other@example.com",
            "password": "correct-horse-battery",
        },
    )
    owner = await db_session.scalar(
        select(User).where(User.email == "guard-owner@example.com")
    )
    other_user = await db_session.scalar(
        select(User).where(User.email == "guard-other@example.com")
    )
    assert owner is not None
    assert other_user is not None

    guard = require_merchant_permission("merchant.account.read")
    membership = await guard(merchant_id, user=owner, session=db_session)
    assert membership.merchant_id == merchant_id

    with pytest.raises(HTTPException) as error:
        await guard(merchant_id, user=other_user, session=db_session)
    assert error.value.status_code == 403
