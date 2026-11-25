# WHO Mongolian retrieval pilot

`questions.jsonl` contains 20 Mongolian questions labelled against the selected
English WHO passages. Labels were fixed before running retrieval. Each label has
an exact source URL and chunk locator, plus its source checksum and text anchor.

```sh
cd backend
HF_HUB_OFFLINE=1 .venv/bin/python -m app.cli evaluate ../data/evaluation/who/questions.jsonl --output ../data/evaluation/results/who-pilot-2026-10-13.json
```

The metric is annotated-passage recall@5. Each question has one labelled passage;
a hit means that passage appears among the first five retrieved chunks. Other
valid passages are not exhaustively annotated, so a miss can undercount useful
retrieval. Labels are provisional technical labels awaiting independent subject
matter review. This small pilot is neither a held-out clinical benchmark nor a
measurement of generated-answer accuracy. No LLM answer is evaluated.

Keep initial labels and results when tuning retrieval. Use a separately reviewed,
larger held-out dataset for thesis claims about generalisation. Raw run output is
saved locally under `data/evaluation/results/`; the progress report records the result.
