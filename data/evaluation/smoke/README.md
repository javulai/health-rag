# Synthetic retrieval smoke test

Ten original, fictional English library documents and 20 questions (10 Mongolian, 10 English).
All paraphrases use the same `smoke` split. Each relevant chunk is labeled by source URL and
locator before retrieval. `example.org` URLs are identifiers, not real sources to fetch.

This checks ingestion, source metadata and cross-language retrieval plumbing using a real
embedding model. It does **not** measure medical accuracy or constitute the thesis evaluation.
Do not add these documents to a real knowledge corpus. Use a separate database ending in `_demo`.
For the thesis, curate approved health documents and separate tuning/test questions.
