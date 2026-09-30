# NCPOR Polar Knowledge Index

Prototype for Smart India Hackathon problem statement **SIH26063** (MoES / NCPOR), Team Anarch.

It harvests what NCPOR has already published (scanned expedition reports on DSpace, the news
feed), reads the scans, links every item to its expedition, station, topic and year, and answers
questions or drafts lessons and announcements **only from cited archive pages**. Every generated
sentence is fact-checked against its source, and nothing is public until a named reviewer
approves it.

## Run it (Windows, PowerShell)

Prerequisites: Python 3.11+, Node 20+, Docker Desktop, Tesseract (`winget install UB-Mannheim.TesseractOCR`).

```powershell
copy .env.example .env                    # then set the database password, GEMINI_API_KEY and LLM_MODEL
powershell -ExecutionPolicy Bypass -File scripts\start-docker.ps1   # Docker + PostgreSQL/pgvector

cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m ingest.rebuild  # migrations, harvest, OCR, links, embeddings, demo users
.\.venv\Scripts\uvicorn app.main:app --port 8010

cd ..\frontend                            # in a second terminal
npm install
npm run dev
```

Open http://localhost:3000. The API runs on port **8010** (8000 is often taken by other projects);
check it at http://localhost:8010/health.

The first `ingest.rebuild` downloads ~265 PDFs from DSpace at one request per second and the
search model (~1 GB), so allow about an hour. Later runs reuse the cache in `data/` and finish in minutes.

**Staff console:** http://localhost:3000/staff. Demo curator and reviewer passwords are written to
`data/demo_users.local.txt` (gitignored). Real accounts: `python -m app.cli create-user`.

## Evaluation

```powershell
cd backend
.\.venv\Scripts\python -m eval.draft_candidates    # AI drafts candidate questions, all "unverified"
.\.venv\Scripts\python -m eval.verify --name "Your Name"   # a person checks each one on the page image
.\.venv\Scripts\python -m eval.run                 # prints citation accuracy and refusal accuracy
```

Only rows a person has verified count. The scores appear at http://localhost:3000/evaluation.

## Tests

```powershell
cd backend; .\.venv\Scripts\python -m pytest -q
```

## Troubleshooting

* **Docker Desktop crashes on start** ("initializing Inference manager" or "Secrets Engine ...
  engine.sock"): run `scripts\start-docker.ps1`. It moves stale socket folders aside and restarts.
* **Gemini "503 high demand"**: temporary overload; the client retries. If it persists, set
  `LLM_MODEL=gemini-2.5-flash` in `.env`.

## Docs

[`docs/architecture.md`](docs/architecture.md) · [`docs/data-model.md`](docs/data-model.md) ·
[`docs/decisions.md`](docs/decisions.md) · [`docs/demo-script.md`](docs/demo-script.md)
