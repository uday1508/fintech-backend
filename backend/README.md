# Fintech Backend

## Local development

From this directory, create and activate a project-local Python environment,
copy `.env.example` to `.env` once, and start PostgreSQL:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
docker compose up -d db
```

Apply migrations and seed roles, permissions, and merchant categories:

```sh
alembic upgrade head
python -m app.scripts.seed_data
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; liveness and readiness checks
are exposed at `/health/live` and `/health/ready`. API documentation is at
`/docs`. Versioned endpoints are under `/api/v1`.

People register with a unique username, email, and password and can log in with
either their username or email at `/api/v1/auth/login`. A merchant is a
workspace owned by a person, not a separate login account: create it while
authenticated using `/api/v1/merchants`, providing its unique business
username/handle. The owner continues to sign in with their personal
username/email and password, and can access the merchant through the returned
workspace.

Tests use the separate `TEST_DATABASE_URL` database. Create it before running
the suite:

```sh
docker compose exec db createdb -U fintech fintech_test
pytest
```

`python -m app.scripts.seed_data` is safe to rerun; it inserts missing reference
data without replacing existing roles or permissions.
