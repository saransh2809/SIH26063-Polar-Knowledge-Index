# Data model

Migrations: `backend/alembic/versions/`. Models: `backend/app/models/`.

| Table | Purpose | Notes |
| --- | --- | --- |
| `sources` | External systems harvested | `dspace`, `ncpor_rss` |
| `items` | One harvested record | `item_type` report/paper/news/video/photo/dataset_link; `original_url` always set; `parent_id` links a paper to its report; unique (`source_id`, `external_id`) prevents duplicates |
| `pages` | Text of one PDF page | `text_origin` text_layer/ocr; `ocr_confidence` 0–100 for OCR pages; `printed_page` as printed on the scan; `image_path` for the page viewer |
| `chunks` | Searchable text piece | Never crosses a page; `tsv` (generated full-text vector, GIN index); `embedding` vector(768), HNSW cosine index |
| `expeditions` | Expeditions named by a harvested record | `code` like ISEA-9, SOE-8, ARC-17, WEDDELL-SEA; `source_url` is the record that names it; `season` only when a source states it |
| `stations`, `topics` | Fixed lists | No station facts are stored without a source |
| `item_links` | Item → exactly one expedition/station/topic/year | `method` rule/model/manual; `status` confirmed/unconfirmed/rejected; `evidence` says why; unique per target, so re-runs never duplicate and never overwrite a curator's decision |
| `users` | Staff accounts | roles curator/reviewer/admin; bcrypt password hashes |
| `drafts` | Generated text | kind answer/lesson/announcement; status ai_draft → auto_checked → approved → published (or rejected); `translation_of_id`; `supersedes_id` + `version` + `correction_note` for corrections |
| `draft_sentences` | One sentence | `section`, `is_claim`, `cited_chunk_ids`, `check_result` supported/partial/unsupported, `check_reason`, `edited_by` |
| `reviews` | Reviewer decisions | reviewer id and name, decision, comment, time |
| `audit_log` | Everything that happened | Append-only: a trigger rejects UPDATE, DELETE and TRUNCATE |
| `eval_questions` | Reserved | The test set lives in `backend/eval/questions.csv` so it can be reviewed in Git |

## Link status meaning

* **confirmed**: NCPOR's own catalogue or printed page says so (report title, the DSpace section a
  paper is filed under, the year in a paper's printed header), or a curator confirmed it.
* **unconfirmed**: our inference (keywords, or the AI fallback). Shown as "Machine-linked
  (unconfirmed)" until a curator confirms or rejects it.

Announcements are built only from items with **confirmed** expedition links.
