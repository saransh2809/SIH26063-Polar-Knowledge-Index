# NCPOR Polar Knowledge Index

Prototype for Smart India Hackathon problem statement **SIH26063** (MoES / NCPOR).

It harvests what NCPOR has already published (scanned expedition reports on DSpace, news),
reads the scans, links every item to its expedition, station, topic and year, and answers
questions or drafts lessons and announcements **only from cited archive pages**. Nothing
generated is public until a named reviewer approves it.

## Run it (Windows, PowerShell)

Prerequisites: Python 3.11+, Node 20+, Docker Desktop, Tesseract (`winget install UB-Mannheim.TesseractOCR`).

```powershell
copy .env.example .env          # then edit .env (database password, Gemini key, model)
docker compose up -d            # PostgreSQL 16 + pgvector
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload
```

Check: open http://localhost:8000/health — expect `"database":"ok"` and a `pgvector` version.

## Docs

See [`docs/`](docs/) for architecture, data model and the decisions log.
