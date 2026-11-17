# Fintech Backend

## Local development

From this directory, copy `.env.example` to `.env`, then start PostgreSQL:

```sh
docker compose up -d db
python -m pip install -e '.[test]'
alembic upgrade head
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; liveness and readiness checks
are exposed at `/health/live` and `/health/ready`.

Tests use the separate `TEST_DATABASE_URL` database. Create it before running
the suite:

```sh
docker compose exec db createdb -U fintech fintech_test
pytest
```
