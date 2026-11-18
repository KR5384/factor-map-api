-- もやもや診断アプリ DB定義（叩き台 2026-11-17）詳細は API・DB定義_叩き台.md
CREATE TABLE IF NOT EXISTS diagnoses (
  -- 基本情報
  diagnosis_id     TEXT PRIMARY KEY,
  status           TEXT NOT NULL DEFAULT 'pre_done'
                   CHECK (status IN ('pre_done','answered','completed')),
  grp              TEXT NOT NULL DEFAULT 'A' CHECK (grp IN ('A','B')),
  is_test          INTEGER NOT NULL DEFAULT 0 CHECK (is_test IN (0,1)),
  consent_version  TEXT NOT NULL,
  client_version   TEXT NOT NULL,
  created_at       TEXT NOT NULL,

  -- 事前アンケート
  pre_frequency    INTEGER CHECK (pre_frequency BETWEEN 1 AND 4),
  pre_explain      INTEGER CHECK (pre_explain BETWEEN 1 AND 5),
  pre_relation     INTEGER CHECK (pre_relation BETWEEN 1 AND 5),
  pre_cause_01     INTEGER CHECK (pre_cause_01 IN (0,1)),
  pre_cause_02     INTEGER CHECK (pre_cause_02 IN (0,1)),
  pre_cause_03     INTEGER CHECK (pre_cause_03 IN (0,1)),
  pre_cause_04     INTEGER CHECK (pre_cause_04 IN (0,1)),
  pre_cause_05     INTEGER CHECK (pre_cause_05 IN (0,1)),
  pre_cause_06     INTEGER CHECK (pre_cause_06 IN (0,1)),
  pre_cause_07     INTEGER CHECK (pre_cause_07 IN (0,1)),
  pre_cause_08     INTEGER CHECK (pre_cause_08 IN (0,1)),
  pre_cause_09     INTEGER CHECK (pre_cause_09 IN (0,1)),
  pre_cause_10     INTEGER CHECK (pre_cause_10 IN (0,1)),
  pre_cause_none   INTEGER CHECK (pre_cause_none IN (0,1)),
  pre_cause_unknown INTEGER CHECK (pre_cause_unknown IN (0,1)),
  age_group        TEXT CHECK (age_group IN ('20s','30s','40s','50plus','no_answer')),

  -- 診断20問
  q01 INTEGER CHECK (q01 BETWEEN 1 AND 5),
  q02 INTEGER CHECK (q02 BETWEEN 1 AND 5),
  q03 INTEGER CHECK (q03 BETWEEN 1 AND 5),
  q04 INTEGER CHECK (q04 BETWEEN 1 AND 5),
  q05 INTEGER CHECK (q05 BETWEEN 1 AND 5),
  q06 INTEGER CHECK (q06 BETWEEN 1 AND 5),
  q07 INTEGER CHECK (q07 BETWEEN 1 AND 5),
  q08 INTEGER CHECK (q08 BETWEEN 1 AND 5),
  q09 INTEGER CHECK (q09 BETWEEN 1 AND 5),
  q10 INTEGER CHECK (q10 BETWEEN 1 AND 5),
  q11 INTEGER CHECK (q11 BETWEEN 1 AND 5),
  q12 INTEGER CHECK (q12 BETWEEN 1 AND 5),
  q13 INTEGER CHECK (q13 BETWEEN 1 AND 5),
  q14 INTEGER CHECK (q14 BETWEEN 1 AND 5),
  q15 INTEGER CHECK (q15 BETWEEN 1 AND 5),
  q16 INTEGER CHECK (q16 BETWEEN 1 AND 5),
  q17 INTEGER CHECK (q17 BETWEEN 1 AND 5),
  q18 INTEGER CHECK (q18 BETWEEN 1 AND 5),
  q19 INTEGER CHECK (q19 BETWEEN 1 AND 5),
  q20 INTEGER CHECK (q20 BETWEEN 1 AND 5),

  -- 診断結果
  scoring_version  TEXT,
  score_01 INTEGER CHECK (score_01 BETWEEN 0 AND 100),
  score_02 INTEGER CHECK (score_02 BETWEEN 0 AND 100),
  score_03 INTEGER CHECK (score_03 BETWEEN 0 AND 100),
  score_04 INTEGER CHECK (score_04 BETWEEN 0 AND 100),
  score_05 INTEGER CHECK (score_05 BETWEEN 0 AND 100),
  score_06 INTEGER CHECK (score_06 BETWEEN 0 AND 100),
  score_07 INTEGER CHECK (score_07 BETWEEN 0 AND 100),
  score_08 INTEGER CHECK (score_08 BETWEEN 0 AND 100),
  score_09 INTEGER CHECK (score_09 BETWEEN 0 AND 100),
  score_10 INTEGER CHECK (score_10 BETWEEN 0 AND 100),
  shown_count      INTEGER CHECK (shown_count BETWEEN 0 AND 4),
  shown_1          INTEGER CHECK (shown_1 BETWEEN 1 AND 10),
  shown_2          INTEGER CHECK (shown_2 BETWEEN 1 AND 10),
  shown_3          INTEGER CHECK (shown_3 BETWEEN 1 AND 10),
  shown_4          INTEGER CHECK (shown_4 BETWEEN 1 AND 10),
  main_category_id INTEGER CHECK (main_category_id BETWEEN 1 AND 10),
  result_type_id   TEXT,
  low_moyamoya     INTEGER CHECK (low_moyamoya IN (0,1)),
  answered_at      TEXT,

  -- 事後アンケート
  post_explain     INTEGER CHECK (post_explain BETWEEN 1 AND 5),
  post_relation    INTEGER CHECK (post_relation BETWEEN 1 AND 5),
  post_fit         INTEGER CHECK (post_fit BETWEEN 1 AND 5),
  post_discovery   INTEGER CHECK (post_discovery BETWEEN 1 AND 5),
  post_comment     TEXT CHECK (post_comment IS NULL OR length(post_comment) <= 200),
  post_at          TEXT
);

CREATE INDEX IF NOT EXISTS idx_diagnoses_created ON diagnoses (created_at);
CREATE INDEX IF NOT EXISTS idx_diagnoses_status  ON diagnoses (is_test, status);
