## Issue

Render staging deploys fail during Alembic startup because SQLAlchemy resolves `postgresql://` to the `psycopg2` dialect by default, while this backend only installs `psycopg[binary]`.

## Why it matters

- hosted staging cannot boot on Render even with valid Postgres and Redis URLs
- deploy debugging is misleading because the DB URL itself is syntactically valid
- the backend should normalize provider URLs into the installed driver format

## Acceptance

- `postgresql://...` env values normalize to `postgresql+psycopg://...`
- already explicit driver URLs are left untouched
- SQLite URLs remain untouched
- backend tests cover the normalization behavior
