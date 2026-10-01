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

Open http://localhost:3000. For a demo, use the production build instead of `npm run dev`:
`npm run build` then `npm start` (faster, no developer overlay). The API runs on port **8010** (8000 is often taken by other projects);
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
* **Gemini "503 high demand" or "429 quota"**: the free tier allows about 20 requests per day per
  model. Enable billing in Google AI Studio, or rely on the local fallback below.

## Language models

Set in `.env`:

| Setting | Recommended | Used for |
| --- | --- | --- |
| `LLM_PROVIDER` | `gemini` | answers, lessons, announcements, fact-checker, Hindi |
| `LLM_FALLBACK_PROVIDER` | `ollama` | tried automatically when Gemini fails (quota, outage, offline) |
| `LLM_BULK_PROVIDER` | `ollama` | link tagging and drafting test questions, so they cost no Gemini quota |

The local model needs [Ollama](https://ollama.com) running with `OLLAMA_MODEL` pulled
(`ollama pull qwen3:8b`, ~5 GB, fits an 8 GB GPU). It works offline but is weaker than Gemini:
in testing it cited every passage for every sentence and its checker was lenient, so keep Gemini
as the main provider when it is available.

## Docs

[`docs/architecture.md`](docs/architecture.md) · [`docs/data-model.md`](docs/data-model.md) ·
[`docs/decisions.md`](docs/decisions.md) · [`docs/demo-script.md`](docs/demo-script.md)
