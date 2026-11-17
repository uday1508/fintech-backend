import jwt
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshSession
from app.auth.tokens import hash_refresh_token


async def test_register_login_refresh_and_current_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "  Ada Lovelace ",
            "username": "Ada_L",
            "email": "ADA@example.com",
            "password": "correct-horse-battery",
        },
    )
    assert registered.status_code == 201
    data = registered.json()["data"]
    assert data["user"]["email"] == "ada@example.com"
    assert data["user"]["full_name"] == "Ada Lovelace"
    assert data["user"]["username"] == "ada_l"
    assert data["wallet_account_id"]

    access_token = data["access_token"]
    refresh_token = data["refresh_token"]
    claims = jwt.decode(access_token, options={"verify_signature": False, "verify_exp": False})
    assert claims["exp"] - claims["iat"] == 15 * 60
    stored_session = await db_session.scalar(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(refresh_token)
        )
    )
    assert stored_session is not None
    assert stored_session.token_hash != refresh_token

    current_user = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert current_user.status_code == 200
    assert current_user.json()["data"]["id"] == data["user"]["id"]

    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refreshed.status_code == 200
    rotated_token = refreshed.json()["data"]["refresh_token"]
    assert rotated_token != refresh_token

    old_token_reuse = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert old_token_reuse.status_code == 401
    assert old_token_reuse.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    logged_out = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": rotated_token},
    )
    assert logged_out.status_code == 200


async def test_duplicate_email_is_conflict(client: AsyncClient) -> None:
    payload = {
        "full_name": "Grace Hopper",
        "username": "grace_h",
        "email": "grace@example.com",
        "password": "correct-horse-battery",
    }

    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    duplicate = await client.post("/api/v1/auth/register", json=payload)

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_duplicate_username_is_conflict(client: AsyncClient) -> None:
    first = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "First User",
            "username": "shared_name",
            "email": "first@example.com",
            "password": "correct-horse-battery",
        },
    )
    second = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Second User",
            "username": "SHARED_NAME",
            "email": "second@example.com",
            "password": "correct-horse-battery",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "USERNAME_ALREADY_TAKEN"


async def test_login_rejects_bad_password(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Katherine Johnson",
            "username": "kjohnson",
            "email": "kj@example.com",
            "password": "correct-horse-battery",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "kjohnson", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_accepts_email_or_username(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Login Test",
            "username": "login_test",
            "email": "login@example.com",
            "password": "correct-horse-battery",
        },
    )

    username_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "login_test", "password": "correct-horse-battery"},
    )
    email_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "correct-horse-battery"},
    )

    for response in (username_login, email_login):
        assert response.status_code == 200
        assert response.json()["data"]["access_token"]


async def test_login_requires_exactly_one_of_email_or_username(
    client: AsyncClient,
) -> None:
    for payload in (
        {"password": "correct-horse-battery"},
        {
            "email": "login@example.com",
            "username": "login_test",
            "password": "correct-horse-battery",
        },
    ):
        response = await client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

