# WHO starter corpus

Batch: `2026-10-12`. Scope: infant and young child feeding, breastfeeding,
caregiver counselling and hygiene. This is a selected starter corpus, not all WHO guidance.

`catalog.json` records official publication URLs, PDF URLs, SHA-256 checksums,
publication dates, licence pages, selected sections and exclusions. Five accepted
PDFs contain 502 physical pages. Four contribute 14 selected pages / 16 sections /
26 retrieval chunks; the fifth (feeding indicators) is a research reference only.
Survey indicators are not indexed as individual feeding prescriptions.

## Reproduce

From the repository root, with the backend environment installed and database migrated:

```sh
backend/.venv/bin/python scripts/who_corpus.py fetch
backend/.venv/bin/python scripts/who_corpus.py prepare
backend/.venv/bin/python scripts/who_corpus.py ingest
```

Review extracted text, source pages, qualifiers and generated chunks before activation:

```sh
backend/.venv/bin/python scripts/who_corpus.py ingest --activate --reviewer YOUR_REVIEWER_LABEL
```

The first model load requires downloading the pinned E5 model. After caching it,
`HF_HUB_OFFLINE=1` permits offline model loading. Database access is still required.
Re-ingestion of unchanged text/model/config reuses the existing document version.
Activation is per document, not an atomic whole-batch operation.

Raw PDFs: `data/raw/who/2026-10-12/`. Prepared text, metadata, page text,
checksums, chunks and ingestion records: `data/processed/who/2026-10-12/`.
These generated files are local and excluded from Git; the catalog and script are retained.

## Attribution and scope

Original works are attributed individually to WHO or WHO/UNICEF in the catalog.
Each accepted PDF includes CC BY-NC-SA 3.0 IGO terms on its recorded licence page.
Selected text has formatting and section-heading adaptations for non-commercial
thesis research; those adaptations use CC BY-NC-SA 4.0. Original PDFs and attribution
are retained. Images and logos are not extracted. No WHO endorsement is implied.
See the [WHO copyright policy](https://www.who.int/about/policies/publishing/copyright)
and each original PDF for applicable terms and third-party material notices.

The candidate *Implementation guidance on counselling women to improve breastfeeding
practices* (2021) is excluded: its PDF rights statement requires permission and does
not match the open-licence assumption. No permission request was sent.

The selected 2023 complementary-feeding recommendations retain their remarks;
alternative-milk recommendations are outside this starter scope. Older historical
recommendation boxes, clinical special cases and unrelated training content are
excluded as recorded in the catalog. Review performed here covers source provenance,
licence and extraction, **not independent clinical validation**. There is no automatic
monitoring for revised or withdrawn guidance.
