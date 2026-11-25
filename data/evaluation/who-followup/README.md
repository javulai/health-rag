# Additional retrieval checks, 2026-11-19

12 author-created Mongolian questions labelled from the active source text before
viewing their retrieval rankings. Weight 0.3 was selected on the existing 20-case
pilot, then evaluated once against these questions. Eight questions concern the
original guidelines and four concern the new systematic review.

This is a small supplementary check on the same corpus, authored by the same agent
that implemented the ranking. It is not independent clinical validation, a blinded
benchmark, or evidence of generalisation to unseen sources. Labels remain provisional.
Keep these labels unchanged for regression checks; create a separately reviewed
larger test set before thesis-wide accuracy claims.

From backend/:

```sh
HF_HUB_OFFLINE=1 .venv/bin/python ../scripts/evaluate_retrieval_variants.py \
  ../data/evaluation/who-followup/questions.jsonl \
  --output ../data/evaluation/results/metadata-followup.json
```
