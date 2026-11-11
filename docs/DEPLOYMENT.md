# Deployment

The API is stateless apart from the database and the `DATA_DIR` report files. It does not need the developer's computer once it is running on a host with PostgreSQL.

## What is prepared

- `Dockerfile` starts Alembic, then Uvicorn on `0.0.0.0:8000`.
- `docker-compose.yml` runs PostgreSQL 16 and the API.
- `/health` checks the database and reports whether Gemini is configured. AI is not required.
- Secrets are environment variables. `.env` is gitignored. `.env.example` lists every variable.
- Optional `QM_API_KEY` requires `X-API-Key` on `/api/*`. `/health` and `/docs` stay open.
- Logs do not include the Gemini key. Row payloads are logged only if `LOG_ROW_PAYLOADS=true`.

## Cloud shape

An affordable fit is one small container (Cloud Run, Fly.io, Railway, or a single VM) plus managed PostgreSQL (Neon, Supabase, RDS, or the Postgres service in the same compose file on a VPS). Do not point production at SQLite on ephemeral disk.

```bash
export GEMINI_API_KEY=   # optional
export QM_API_KEY=choose-a-long-random-value
docker compose up --build
```

The compose file publishes port 8000. Put TLS in front of it. Change the compose database password before any public deploy.

## What this environment could not verify

Docker and PostgreSQL are not installed on the development machine used for this build. Migrations were applied to local SQLite (`alembic upgrade head`). A live cloud deploy was not performed because it needs an account and a host. The container definition is ready; it has not been booted here.

## Gemini

Set `GEMINI_API_KEY` to a Google AI Studio key. The client calls the Generative Language REST API with `httpx`. No key is baked into the image if you pass it only at runtime. If the key is missing, `/api/ai/explain` uses the deterministic fallback and the rest of the API is unchanged.
