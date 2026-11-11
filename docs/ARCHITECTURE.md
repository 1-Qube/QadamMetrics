# Architecture

QadamMetrics is a backend intelligence engine. The future React UI should consume the JSON API. It should not need a new analytical core.

## Layers

1. `app/api/routes.py` validates HTTP input and returns a `{data}` or `{error}` envelope.
2. `app/services/analytics_service.py` loads one dataset from SQLAlchemy and calls the engines.
3. `app/analytics/*` are pure functions. They do not import FastAPI or the database.
4. `app/ai/copilot.py` may narrate engine JSON. It is not allowed to calculate new statistics.
5. `app/reporting/engine.py` turns those same objects into JSON, PDF, and CSV. Reports are aggregates only.

Dataset isolation is `dataset_id` on every row. External school identifiers are never treated as global keys.

## Database

SQLAlchemy models in `app/models/entities.py` are the schema. They use portable types (string ids, JSON) so the same models run on SQLite and PostgreSQL.

- Local default: `sqlite:///./data/qadammetrics.db`
- Production: `postgresql+psycopg://...`
- Alembic revision `001_initial` creates the model metadata.
- `AUTO_CREATE_TABLES=true` also creates tables on startup for zero-dependency local use. Set it false in production and run Alembic.

SQLite is a development and test convenience. It is not the intended multi-user production database.

## What is intentionally not in this phase

No dashboard, branding, or frontend build. Swagger UI at `/docs` is the inspection surface.
