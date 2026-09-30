# Decisions log

Each entry: what we chose, the alternative, and why.

## 2026-09-30 — Gemini instead of the Anthropic API
The build brief named the Anthropic SDK. The team has a Gemini key, so the LLM layer uses
Google's official `google-genai` SDK with the model name in `LLM_MODEL`. Only answer writing,
drafting, checking and translation depend on the LLM; embeddings run locally.

## 2026-09-30 — Database on host port 5433
Avoids clashing with a locally installed PostgreSQL on 5432.

## 2026-09-30 — Audit log enforced by a database trigger
`audit_log` rejects UPDATE, DELETE and TRUNCATE at the database level, so even a bug in the
API cannot rewrite history. Alternative (append-only by convention in code) is weaker.

## 2026-09-30 — Report / paper hierarchy (`items.parent_id`)
DSpace stores each expedition report as a *community* whose section *collections* hold one
*item per paper*, each with its own PDF. We store the report as an `items` row of type
`report` and each paper as type `paper` pointing to it. This gives "chunk by paper" for free.

## 2026-09-30 — Separate `pages` table and `printed_page`
Page text is stored per PDF page so the UI can show text beside the page image, and the
evaluation can check the expected page. PDF page 1 of a paper is not the page printed in the
report (e.g. 239), so `printed_page` stores the printed number when OCR can read it.

## 2026-09-30 — DSpace via OAI-PMH, with lenient XML parsing
Reconnaissance (`backend/ingest/recon.py`) found OAI-PMH at `/dspace-oai/request` and no
robots.txt on the DSpace host. The server emits unescaped `&` in set names, so XML is parsed
with a recovering parser. OAI `oai_dc` records do not carry PDF links, so the harvester reads
each item's public page once to find its bitstream URL. `dc:date` is the DSpace accession date
(2006), not the publication date, so it is kept in `raw_metadata` only.

## 2026-09-30 — NPDC is not harvested
The brief says NPDC's robots.txt disallowed automated access. On 30 Sep 2026 it read
`Allow: /`, but we keep NPDC out of scope until NCPOR gives permission.
