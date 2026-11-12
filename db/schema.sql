PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS variants (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  exam_year INTEGER NOT NULL,
  variant_number TEXT NOT NULL,
  source_path TEXT NOT NULL UNIQUE,
  source_sha256 TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  is_official_demo INTEGER NOT NULL DEFAULT 0,
  imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS variant_sources (
  variant_id TEXT NOT NULL REFERENCES variants(id),
  source_role TEXT NOT NULL CHECK (source_role IN ('answer_key','criteria','pdf_copy')),
  source_path TEXT NOT NULL UNIQUE,
  source_sha256 TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  PRIMARY KEY (variant_id, source_role, source_path)
);

CREATE TABLE IF NOT EXISTS problems (
  id TEXT PRIMARY KEY,
  variant_id TEXT NOT NULL REFERENCES variants(id),
  problem_number INTEGER NOT NULL CHECK (problem_number BETWEEN 1 AND 26),
  alternative_number INTEGER NOT NULL DEFAULT 1,
  statement TEXT NOT NULL,
  statement_format TEXT NOT NULL DEFAULT 'plain_with_latex',
  answer TEXT,
  solution TEXT,
  criteria TEXT,
  max_points INTEGER NOT NULL,
  answer_format TEXT NOT NULL,
  topic TEXT NOT NULL,
  extraction_status TEXT NOT NULL CHECK (extraction_status IN ('verified','needs_review')),
  review_notes TEXT,
  source_locator TEXT NOT NULL,
  UNIQUE (variant_id, problem_number, alternative_number)
);

CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  media_type TEXT NOT NULL,
  storage_path TEXT NOT NULL UNIQUE,
  sha256 TEXT NOT NULL UNIQUE,
  size_bytes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS problem_assets (
  problem_id TEXT NOT NULL REFERENCES problems(id),
  asset_id TEXT NOT NULL REFERENCES assets(id),
  role TEXT NOT NULL CHECK (role IN ('source_page','statement_figure','solution_figure')),
  source_locator TEXT,
  PRIMARY KEY (problem_id, asset_id, role)
);

CREATE TABLE IF NOT EXISTS exam_positions (
  exam_year INTEGER NOT NULL,
  problem_number INTEGER NOT NULL CHECK (problem_number BETWEEN 1 AND 26),
  topic TEXT NOT NULL,
  answer_format TEXT NOT NULL,
  max_points INTEGER NOT NULL,
  specification_status TEXT NOT NULL,
  PRIMARY KEY (exam_year, problem_number)
);

CREATE TABLE IF NOT EXISTS relevance (
  problem_id TEXT NOT NULL REFERENCES problems(id),
  exam_year INTEGER NOT NULL,
  target_problem_number INTEGER NOT NULL,
  topic_match INTEGER NOT NULL,
  format_match INTEGER NOT NULL,
  verdict TEXT NOT NULL CHECK (verdict IN ('yes','no','partial')),
  reason TEXT NOT NULL,
  assessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (problem_id, exam_year, target_problem_number),
  FOREIGN KEY (exam_year, target_problem_number) REFERENCES exam_positions(exam_year, problem_number)
);

CREATE INDEX IF NOT EXISTS problems_variant_idx ON problems(variant_id, problem_number);
CREATE INDEX IF NOT EXISTS relevance_target_idx ON relevance(exam_year, target_problem_number, verdict);
