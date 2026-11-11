# Deployment

QadamMetrics is meant to run without the development laptop. The frontend is a Next.js app. The API is FastAPI. PostgreSQL holds datasets, textbooks, and report JSON. Gemini is called only by the API.

This file is the setup record. It does not claim a live URL until one has been verified from a public host.

## Architecture

```text
judge browser
    |
    | HTTPS
    v
Vercel  (frontend/)
    |
    | NEXT_PUBLIC_API_URL  (public API address only)
    v
Render  (Dockerfile, this repo)
    |
    | DATABASE_URL via SSL
    v
Supabase PostgreSQL

Render also calls Gemini with GEMINI_API_KEY.
That key never goes to the browser or to Git.
```

CSV rows and textbook text are stored in Postgres. Report JSON is stored on the `reports.summary` column, so a container restart does not erase a generated report. PDF and CSV files are rebuilt from that JSON if the container disk is empty.

## What is not done from this machine

As of the last check:

- `vercel` is installed but logged out.
- `render` and `supabase` CLIs are not installed and no API tokens are in the environment.
- No public frontend URL, backend URL, or Supabase project was created.
- No paid plan was purchased.

Do not treat a local `http://127.0.0.1` address as production.

## Accounts you need to create

These are free-tier capable. Do not enter a card unless you choose to.

1. https://vercel.com — sign up with the GitHub account `1-Qube`.
2. https://render.com — sign up with the same GitHub account.
3. https://supabase.com — sign up, create a project named `qadammetrics` in a nearby region.
4. https://aistudio.google.com/apikey — create a Gemini key. Paste it only into Render, not into Git or the frontend.

## 1. Supabase

In the Supabase project:

1. Open **Project Settings → Database**.
2. Copy the **URI** connection string.
3. Change the scheme to `postgresql+psycopg://` and add SSL:

```text
postgresql+psycopg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres?sslmode=require
```

Use the direct host (port 5432) for this app. The transaction pooler on port 6543 is optional and is supported (`prepare_threshold` is disabled when the URL contains `:6543` or `pooler.supabase.com`).

Do not use the `service_role` key in the frontend. The API uses `DATABASE_URL` only.

Alembic creates the schema on container start (`alembic upgrade head`). You do not paste SQL by hand.

## 2. Render

1. **New → Blueprint** and select the GitHub repo `1-Qube/QadamMetrics`. Render reads `render.yaml`.
2. When it asks for secret values, set:

| Key | Value |
| --- | --- |
| `DATABASE_URL` | the Supabase URI from above |
| `GEMINI_API_KEY` | the Google key, or leave blank for the deterministic copilot |
| `CORS_ORIGINS` | the Vercel URL, for example `https://qadammetrics.vercel.app` |
| `QM_API_KEY` | leave blank for the judge demo |

3. Confirm `ENVIRONMENT=production`, `AUTO_CREATE_TABLES=false`, `SEED_DEMO=true`.
4. Deploy. The first boot runs migrations and loads one public synthetic dataset. That can take a few minutes on the free instance.
5. Open `https://YOUR-SERVICE.onrender.com/health`. It must show `"database":"up"`. `/docs` is the API reference.

Free Render web services sleep after about 15 minutes without traffic. The first judge request can take 30–60 seconds. That is the main reliability limit. A paid Render instance (about $7/month) stays awake. Do not turn that on unless you approve the charge.

## 3. Vercel

From `frontend/` after `npx vercel login`:

```bash
cd frontend
npx vercel link
npx vercel env add NEXT_PUBLIC_API_URL production
npx vercel --prod
```

Set `NEXT_PUBLIC_API_URL` to the Render origin with no trailing slash, for example `https://qadammetrics-api.onrender.com`.

Do not set `GEMINI_API_KEY` or `DATABASE_URL` on Vercel. The browser only needs the public API address.

Then put that Vercel origin into Render `CORS_ORIGINS` and redeploy the API if the first value was a guess. Production rejects `CORS_ORIGINS=*`.

## 4. GitHub

The repo is private: https://github.com/1-Qube/QadamMetrics

Connect that repo in both Vercel and Render so a push to `main` redeploys. Environment variables stay in each host's dashboard. GitHub Actions does not receive them.

`.env` is gitignored. `.env.example` has names only.

## Judge path

1. Open the Vercel URL.
2. If the database was seeded, the synthetic mathematics dataset is already listed and labeled synthetic.
3. Otherwise use **Load synthetic demo** on the Data page. That calls the real generator in the cloud. Results are not hardcoded.
4. Topics, knowledge map, textbooks, planning, and reports call the API. Planning reruns SciPy when the sliders change.
5. The copilot calls Gemini only if Render has `GEMINI_API_KEY`. If the key is missing or Gemini fails, the deterministic explanation is used and the rest of the API still works.
6. A private CSV upload is stored under a random owner token kept in that browser's localStorage (`qm.ownerToken`). Another browser cannot list it. The public demo can.

No admin password is shipped in the frontend.

## Local check before you push

```powershell
cd C:\Users\Nomad\QadamMetrics
.\.venv\Scripts\python.exe -m pytest
cd frontend
npm install
npm run build
```

Copy `.env.example` to `.env` for local SQLite. Do not point local `.env` at production unless you intend to.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Health says database down | `DATABASE_URL` scheme is `postgresql+psycopg`, password is URL-encoded, `sslmode=require` is present, Supabase project is not paused. |
| Browser error about CORS | `CORS_ORIGINS` is exactly the Vercel origin, including `https://`, with no path. |
| API cold for a minute | Render free tier sleep. Open `/health` once, then the app. |
| Copilot says the key is not set | `GEMINI_API_KEY` is empty on Render. Analytics still work. |
| Upload returns 415 | Responses must be `.csv`. Textbooks must be `.txt` or `.pdf`. |
| Upload returns 429 | The per-IP limit fired. Wait a minute. |
| Report download works after a restart | Expected. The JSON is in Postgres; PDF/CSV are rebuilt. |
| Production process exits on boot | Logs will say SQLite, `CORS_ORIGINS=*`, or `AUTO_CREATE_TABLES=true`. Fix the env var. |

## Cost

| Piece | Free tier | If you approve a charge |
| --- | --- | --- |
| Vercel hobby | $0 for this app | not required |
| Render web | $0, sleeps | about $7/month to stay awake |
| Supabase | $0 until the project pauses | about $25/month Pro if the free project pauses |
| Gemini | Google's free quota, then their rates | depends on traffic |

No charge was started from this workspace.

## Updating

Push to `main`. Render and Vercel rebuild if the GitHub connection is in place. Schema changes belong in a new Alembic revision. Do not rely on `AUTO_CREATE_TABLES` in production.
