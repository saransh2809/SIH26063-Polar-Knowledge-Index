export type Hit = {
  chunk_id: number;
  item_id: number;
  page: number;
  printed_page: string | null;
  text: string;
  item_title: string;
  report_title: string | null;
  original_url: string;
  file_url: string | null;
  page_image: string | null;
  text_origin: "text_layer" | "ocr" | "mixed";
  ocr_confidence: number | null;
  keyword_rank: number | null;
  vector_rank: number | null;
  similarity: number | null;
  score: number;
};

export type Link = {
  id: number;
  item_id: number;
  type: "expedition" | "station" | "topic" | "year";
  label: string;
  code: string | null;
  method: "rule" | "model" | "manual";
  status: "confirmed" | "unconfirmed" | "rejected";
  state: string;
  evidence: string | null;
  confirmed_by: string | null;
  confirmed_at: string | null;
};

export type ItemSummary = {
  id: number;
  type: string;
  title: string;
  original_url: string;
  file_url: string | null;
  source: string | null;
  published_date: string | null;
  page_count: number | null;
  section: string | null;
  authors: string[];
  parent_id: number | null;
};

export type Sentence = {
  id: number;
  seq: number;
  section: string | null;
  text: string;
  is_claim: boolean;
  citations: number[];
  check_result: "supported" | "partial" | "unsupported" | null;
  check_reason: string | null;
  edited_by: string | null;
};

export type Citation = {
  chunk_id: number;
  item_id: number;
  page: number;
  printed_page: string | null;
  item_title: string;
  report_title: string | null;
  original_url: string;
  page_image: string;
  text: string;
  text_origin: string;
  ocr_confidence: number | null;
};

export type Draft = {
  id: number;
  kind: "answer" | "lesson" | "announcement" | "social_post";
  title: string;
  audience: string | null;
  language: "en" | "hi";
  status: "ai_draft" | "auto_checked" | "approved" | "rejected" | "published";
  state: string;
  created_by: string;
  created_at: string;
  published_at: string | null;
  version: number;
  supersedes_id: number | null;
  correction_note: string | null;
  translation_of_id: number | null;
  expedition_id: number | null;
  params: Record<string, unknown>;
  approved_by: string | null;
  approved_at: string | null;
  reviews: { reviewer: string; decision: string; comment: string | null; at: string }[];
  translations: { id: number; language: string; status: string }[];
  sentences: Sentence[];
  sources: Citation[];
  check_summary: { supported: number; partial: number; unsupported: number };
  history?: { id: number; version: number; published_at: string | null }[];
  superseded_by?: number | null;
};

export type ExpeditionRow = {
  code: string;
  number: number | null;
  name: string;
  region: string;
  season: string | null;
  source_url: string | null;
  report: "published" | "listed, not published" | "none found";
  papers: number;
  papers_extracted: number;
  datasets: number;
  photos: number;
  news: number;
  videos: number;
  public_stories: number;
  inferred?: boolean;
};
