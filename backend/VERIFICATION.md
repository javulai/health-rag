# Verification — 2026-10-12

## Login and generated chat — 2026-10-26

- Next.js production build and TypeScript check passed.
- Backend suite: **34 passed** with dedicated thesis_test database.
- Ruff import ordering corrected; format check passed (38 files).
- Live request through Next.js proxy: login 200, chat 200, logout 200.
- OpenAI credit issue resolved after user added credit. Real Mongolian answer
  with WHO citation returned in 10.3 seconds for a breastfeeding question.
- Tests cover authentication, session expiry/revocation, CSRF, login rate limit,
  mocked Responses requests, citation validation and authenticated chat.
- This verifies the application flow, not clinical accuracy or general answer quality.
- Local single-account sessions and nonpersistent, independent chat questions only.

## Initial infrastructure checks

- Host: macOS ARM64, Python 3.11.7; local PostgreSQL 17 with pgvector 0.8.1 in Docker.
- `pytest -q` with a dedicated `thesis_test` database: **20 passed**.
- Ruff lint and format checks passed.
- CPU-only backend Docker image built successfully; Compose migration exited successfully.
- Live `GET http://127.0.0.1:8000/health/ready` returned HTTP 200 with database `ok`
  and schema `0001_knowledge`. The Docker one-shot worker CLI `--help` also succeeded.
- Tests cover parsing and chunk coverage, metadata/vector validation, health failures,
  staging isolation, activation, source disable filtering, duplicate/concurrent ingestion,
  version retirement, model-revision mismatch, incomplete embeddings and migration/schema parity.
- Unit/integration tests use a deterministic **test-only** embedding double.
- Separately ran **real** `intfloat/multilingual-e5-small` on 10 synthetic English documents
  with 10 Mongolian and 10 English questions in `thesis_demo`.
- Pinned model revision: `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- Synthetic retrieval result: **recall@5 = 1.0 (20/20 questions)**.
- Raw local results: `../data/evaluation/results/smoke.json` (excluded from Git).
- An additional Mongolian CLI query with Hugging Face offline mode returned the expected
  English source as its first result; saved locally as `search-example.json` beside smoke results.

The synthetic result is a pipeline smoke test on a small corpus, not a measurement of health
advice accuracy, grounded answer quality, production performance or the thesis acceptance criteria.
At that initial smoke-test stage the main `thesis` corpus was empty.

## WHO pilot — 2026-10-13

- Main `thesis` corpus: 4 active WHO document versions, 26 chunks; one additional
  PDF retained only as a research reference. Re-ingestion reused all four versions.
- 20 pre-labelled Mongolian questions: annotated-passage recall@5 **0.55 (11/20)**.
  Provisional technical labels, not independent clinical validation or answer accuracy.
- Unit/integration suite: **28 passed**; Ruff lint and format checks passed.
- Rebuilt Docker image; API and database healthy; readiness HTTP 200, schema `0001_knowledge`.
- No LLM-generated answers are implemented yet.
- [Full progress report](../report/progress-2026-10-13.md),
  [dataset methodology](../data/evaluation/who/README.md),
  local raw result `../data/evaluation/results/who-pilot-2026-10-13.json`.

## WHO review expansion: 2026-11-19

- Activated one review, four chunks; total five documents / 30 chunks.
- Same pilot recall@5: before 0.55, after 0.45. No retrieval algorithm changes.
- Two Mongolian and one English smoke query returned the new source first.
- No generated-answer or clinical assessment in this run.
- [Detailed findings](../report/progress-2026-11-19.md).

## Heading-aware retrieval: 2026-11-19

- Existing 20-case pilot: content-only 9/20, weight 0.3 13/20.
- Supplementary 12-case set: content-only 5/12, weight 0.3 7/12.
- No previous top-5 hits lost in these sets; failures remain.
- Production search path reproduced both results. Final output remains top-5.
- 36 tests passed with dedicated thesis_test DB; Ruff lint/format passed.
- Added tests for reranking beyond the final limit, baseline rollback, disabled-source
  filtering and heading-cache invalidation by text. Embedding doubles are test-only.
- Pilot median retrieval latency: 24 ms baseline / 26 ms blended on this local run.
  This excludes model load, is not a load test, and does not represent cold-start latency.


## 2026-11-19: persistent auth/history

39 tests passed (9 PostgreSQL integration); Ruff and frontend production build passed.
See ../report/implementation-2026-11-19.md. Live generation rerun with replacement key: 10/10 responses, 9/10 expected behavior.
Source-text review found wording/qualifier/relevance errors; not clinical accuracy.
Real Next.js proxy → API → OpenAI → persisted two-message history check passed.


## 2026-11-20: sentence evidence and stronger review

42 tests passed, including per-sentence evidence requirements and reviewer rejection.
Final generation: paired 10/10 behavior; fresh 9/12. See ../report/quality-and-corpus-2026-11-20.md.

## 2026-11-26 — бүртгэл ба Google ID token

- `pytest tests/unit -q`: 36 passed (SQLite auth tests, Google token verifier mocked).
- `pytest tests/integration -q`: 9 passed against disposable `thesis_test` PostgreSQL.
- Ruff check: changed auth modules, migration, new tests passed.
- Frontend `npm run build`: passed; registration form visually reviewed.
- Local schema upgraded to `0003_google`; 37 active chunks preserved.
- Live Next.js proxy: login page 200, malformed registration 422; API readiness ready.
- `GOOGLE_CLIENT_ID` is not configured: real Google account sign-in remains untested; Google button intentionally hidden. Setup: GOOGLE-LOGIN.md.
