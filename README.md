# QadamMetrics

Curriculum intelligence engine for methodologists. It ingests assessment data, describes topic performance with uncertainty, reviews a knowledge graph, compares textbook structure, explores hour allocations under explicit assumptions, and refuses causal certainty it cannot earn.

This repository is the backend plus a Next.js dashboard in `frontend/`. Locally, use `/docs` or the dashboard. Cloud setup is in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). A public URL is not claimed until Vercel, Render, and Supabase have been connected.

Synthetic demonstration data is labeled `evidence_class: synthetic`. It is not evidence about real students.

## Run locally

From `C:\Users\Nomad\QadamMetrics` in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000/docs and http://127.0.0.1:8000/health.

Load the synthetic demo:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/datasets/demo"
```

Regenerate the checked-in CSV files:

```powershell
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe scripts\generate_demo_data.py
.\.venv\Scripts\python.exe scripts\summarize_demo.py
```

The virtual environment was created with `uv` and Python 3.13. To recreate it:

```powershell
uv venv --python 3.13 .venv
uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt
```

Copy `.env.example` to `.env` if you want PostgreSQL or Gemini. The default SQLite file is `data/qadammetrics.db`. Tables are created on startup when `AUTO_CREATE_TABLES=true`.

## What the API does

| Area | Route prefix | Role |
| --- | --- | --- |
| Ingestion | `/api/datasets` | CSV validation, issues, import history, demo loader |
| Diagnostics | `/api/analytics` | Topic accuracy, intervals, coverage, school and time splits |
| Graph | `/api/knowledge-graph` | Verified edges, inferred candidates, risk hypotheses |
| Textbooks | `/api/textbooks`, `/api/textbook-comparison` | PDF/text structure, not effectiveness |
| Flight simulator | `/api/optimization` | SciPy hour scenarios under labeled assumptions |
| Contrast | `/api/causal-analysis` | Association or adjusted estimate, never a causal conclusion |
| Decisions | `/api/recommendations` | Rule-based review steps grounded in engine output |
| Reports | `/api/reports` | JSON, PDF, and CSV zip |
| Copilot | `/api/ai` | Gemini if configured, otherwise a deterministic fallback |

Details and example bodies are in [docs/API.md](docs/API.md). Methods are in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Tests

`pytest` covers ingestion, validation, duplicates, small versus large samples, Wilson intervals, graph cycles, inferred-edge labeling, infeasible optimization, textbook extraction, nested-treatment refusal, recommendation guardrails, missing API keys, report generation, dataset isolation, and the demo API path.

On this machine the last full run was 30 passed. Re-run before relying on that count.

## Dashboard

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The API defaults to http://127.0.0.1:8000. Set `NEXT_PUBLIC_API_URL` for any other host. Do not put `GEMINI_API_KEY` in the frontend.

## Production

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). The intended hosts are Vercel, Render, and Supabase PostgreSQL. Secrets stay in those dashboards. `.env` is not committed.

Set `GEMINI_API_KEY` only on the API host. The platform works without it. Production refuses SQLite and `CORS_ORIGINS=*`.

## Limits

- Custom difficulty indexes are descriptive, not validated psychometric scales.
- Optimization does not fit a learning-response curve from the upload.
- Textbook keyword extraction is a heuristic.
- Causal conclusions are not produced.
- Student-level intervals ignore school clustering.
- Demo patterns exist because the generator put them there. Read [docs/SYNTHETIC_DATA.md](docs/SYNTHETIC_DATA.md) before showing the demo as if it were a discovery about real schools.
