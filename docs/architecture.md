# Architecture

One Python backend, one PostgreSQL database, one Next.js web app. Records flow *down* from
NCPOR's existing systems into the index; the originals are never copied into a new store.

```
 NCPOR systems (unchanged)            Index (this project)                     People
 ─────────────────────────            ────────────────────                     ──────
 DSpace (OAI-PMH + item pages) ──┐
 NCPOR news RSS feed ────────────┼─> harvesters ─> items ─> extract/OCR ─> pages, chunks
                                 │     (polite,     │                          │
 NPDC (not harvested: needs      │      cached)     └──> linker ──> item_links  │
 NCPOR permission)               │                       (rules, then AI,      │
                                 │                        unconfirmed)         ▼
                                 │                               embeddings + full-text index
                                 │                                            │
                                 │                           hybrid search (RRF) ─> public: search, ask,
                                 │                                            │         page viewer, expeditions,
                                 │                                            │         coverage, lessons
                                 │                  grounded generators ─> checker ─> review queue ─> publish
                                 │                  (Gemini, cited)       (per sentence)  (named reviewer)
```

## Components

| Part | Where | What it does |
| --- | --- | --- |
| Polite HTTP client | `backend/ingest/http.py` | robots.txt, ≤1 request/second, on-disk cache, rejects empty bodies |
| DSpace harvester | `backend/ingest/dspace.py` | Reports (communities) and papers (items) via OAI-PMH; PDF link from each item page |
| News harvester | `backend/ingest/news.py` | 837 posts from the RSS feed; expeditions named in posts get their own records |
| Extraction | `backend/ingest/extract.py` | Text layer when usable, else Tesseract OCR; page images; printed page numbers; page-bounded chunks |
| Linker | `backend/ingest/linker.py` | Expedition/station/topic/year links; rules first, Gemini fallback for the rest |
| Embeddings | `backend/ingest/embed.py`, `app/services/embeddings.py` | `multilingual-e5-base` on CPU, 768 numbers per chunk |
| Search | `app/services/search.py` | PostgreSQL full-text + pgvector, fused by Reciprocal Rank Fusion |
| Generators | `app/services/generators.py` | Cited answers, lesson units, announcements, Hindi translation |
| Checker + workflow | `app/services/drafts.py` | Per-sentence faithfulness check; approve/reject/publish; corrections as new versions |
| API | `app/api/public.py`, `app/api/staff.py` | Public is read-only; staff endpoints need a login and a role |
| Web | `frontend/` | Next.js App Router; public pages are server-rendered |
| Evaluation | `backend/eval/` | Test set CSV, human verification CLI, scoring run |

## Where AI is used, and how errors are contained

| Use | Control |
| --- | --- |
| Link classification fallback | Chooses only from fixed lists; always *unconfirmed*; evidence quote stored |
| Cited answers, lessons, announcements | Model sees only retrieved passages; citations outside them are dropped; refusal when retrieval is weak or the model says the passages do not answer |
| Faithfulness check | Every claim sentence judged against its cited passages; unsupported sentences block approval |
| Hindi translation | Translated from an approved English draft; checked again; needs its own approval |

Nothing generated is public until a user with the reviewer role approves and publishes it.
Every step writes to `audit_log`, which a database trigger makes append-only.

## Public question answering and the review rule

The build brief requires that no generated text is public before review. The public *Ask* page
therefore shows (a) the matching archive passages verbatim, which are NCPOR's own words, and
(b) an AI answer only if a reviewer has approved one for that question. Staff generate and
review new answers in the staff console.
