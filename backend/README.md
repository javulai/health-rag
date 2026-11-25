# RAG — эхний шат

Энэ шат нь баримт → текст → chunk → embedding → PostgreSQL → асуултын хайлт гэсэн урсгал.
OpenAI Монгол хариулт, локал нэвтрэлт, Next.js чат UI хэрэгжсэн. [Чат ажиллуулах заавар](../frontend/README.md). Олон хэрэглэгч, байнгын чат түүх хэрэгжсэн; queue worker хараахан хэрэгжээгүй.
`report/` доторх дипломын файлуудыг мэдлэгийн санд автоматаар оруулахгүй.

## 1. Локал орчин (хөгжүүлэлтэд санал болгох зам)

Docker/OrbStack ажиллаж байх шаардлагатай. Python 3.11 ба `uv` ашиглана.
Төслийн root-оос:

```sh
# .env байхгүй үед л хуулна. Байгаа тохиргоогоо дарж бичихгүй.
test -f .env || cp .env.example .env
docker compose --env-file .env -f infra/compose.yaml up -d db
cd backend
uv sync --frozen --extra embedding
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

- API: http://127.0.0.1:8000/docs
- `/health`: процесс ажиллаж буй эсэх.
- `/health/ready`: DB, pgvector, migration шалгана. Model татагдсан эсэхийг шалгахгүй.
- PostgreSQL: `127.0.0.1:55432`, database `thesis`.
- `.env.example`-ийн нууц үг зөвхөн локал хөгжүүлэлтэд зориулагдсан.
- DB өгөгдөл `thesis-rag_postgres_data` volume-д хадгалагдана.
- `docker compose ... down` container-уудыг зогсооно; `down -v` өгөгдлийг устгана.

## 2. Бүгдийг Docker-оор ажиллуулах

Төслийн root-оос:

```sh
docker compose --env-file .env -f infra/compose.yaml up --build -d api
```

`db` бэлэн болсны дараа `migrate` нэг удаа ажиллаж, амжилттай үед `api` асна.
Host дээрх API ба Docker API хоёрыг нэг порт дээр зэрэг асаахгүй.
`worker` нь `tools` profile доторх нэг удаагийн CLI процесс; queue consumer биш.

```sh
docker compose --env-file .env -f infra/compose.yaml run --rm worker --help
```

Доорх CLI жишээний `uv run --extra embedding python -m app.cli`-ийн оронд энэ `docker compose ... run --rm worker` командыг ашиглаж болно. Container дотор баримтын зам `/data/raw/...`, evaluation өгөгдөл `/data/evaluation/...` байна. Host ба container-ийн model cache тусдаа; эхний хэрэглээнд тус бүр загвараа татна.

## 3. Баримт оруулах → шалгах → идэвхжүүлэх

Дэмжих төрөл: UTF-8 `.txt`, `.md`, текст задлах боломжтой `.pdf`. OCR, хүснэгтийн тусгай parser,
URL crawler хараахан байхгүй. Зураг хэлбэрийн PDF-д OCR-ийг урьдчилан хийнэ. PDF-ийн extractable
text хэсгийг л боловсруулдаг учир хоосон/зурагтай хуудас, хүснэгт, өгүүлбэрийн дарааллыг reviewer шалгана.
Нэг файл 20 MiB, 5000 chunk хүртэл. URL нь эх сурвалжийн metadata; сервер URL-ийг татахгүй.

Эх баримтаа `data/raw/guide.md`, metadata-г `data/raw/guide.json` гэж байрлуулна. Metadata жишээ:

```json
{
  "url": "https://example.org/replace-with-approved-source",
  "title": "Баримтын бодит гарчиг",
  "organization": "Нийтэлсэн байгууллага",
  "language": "mn",
  "topic": "Сонгосон сэдэв",
  "reuse_note": "Дахин ашиглах нөхцөл, шалгасан тэмдэглэл",
  "published_at": null,
  "updated_at": null
}
```

`backend/` дотроос:

```sh
uv run --extra embedding python -m app.cli ingest ../data/raw/guide.md --metadata ../data/raw/guide.json
uv run --extra embedding python -m app.cli inspect VERSION_UUID
uv run --extra embedding python -m app.cli activate VERSION_UUID --reviewer your-name
uv run --extra embedding python -m app.cli search "Тухайн баримттай холбоотой асуулт" --limit 5
```

`VERSION_UUID`-г ingest-ийн бодит гаралтаар солино. `inspect`-ийн текст, locator, token_count-ыг
эх баримттай харьцуулж шалгаад `activate` ажиллуулна. Шалгасан гэдгийг CLI ашиглаж буй хүн хариуцна.

- Баримтын checksum-тай хуулбар `data/raw/` дотор хадгалагдана.
- Ижил URL + checksum + model revision + chunk тохиргоог давтан оруулахад өмнөх version ID буцна.
- Шинэ хувилбар `staging`; өмнөх `active` хайлтад ажилласаар байна.
- Идэвхжүүлэлт хуучныг `retired` болгоод шинийг нэг гүйлгээнд `active` болгоно. Хуучин chunk устахгүй.
- Хайлт зөвхөн `enabled` source-ийн `active` хувилбарыг ашиглана.
- Үр дүнд chunk ID, version ID, текст, эх URL, гарчиг, байгууллага, locator, cosine score гарна.
- Cosine score бол эрэмбэлэх оноо; үнэн зөвийн магадлал биш. LLM supported=false буцаавал баримт хангалтгүй гэсэн хариулт өгнө.

## 4. Embedding тохиргоо

Baseline: `intfloat/multilingual-e5-small`, 384 хэмжээ, CPU, `query:` / `passage:` prefix,
нормчилсон embedding. Эхний хэрэглээнд Hugging Face-ээс загвар татна; төлбөртэй API түлхүүр хэрэггүй.
`data/models/` cache Git-д орохгүй. Дараагийн ажиллуулалт cache ашиглана.

Chunk нь model-ийн tokenizer-аар 400 token хүртэл, 50 token давхцалтай. Markdown paragraph/heading,
PDF хуудасны хил хадгална; урт хэсгийг sentence boundary-д ойр тасална. Хэсэгт багтахгүй урт асуултыг
чимээгүй тайрахгүй, алдаа буцаана. Баримтын төгсгөл, Unicode, хүснэгтийн чанарыг review-ээр шалгана.

`EMBEDDING_REVISION`-г анх model-ийн commit ID-д тогтоож хэрэглэнэ. Код version metadata-д бодит
resolved commit-ийг хадгална; асуултын model ба corpus-ийн revision зөрвөл алдаа өгнө.
Model/хэмжээ солихдоо тусдаа сан эсвэл төлөвлөсөн reindex/migration хэрэгтэй.

Техникийн лавлагаа: [E5 model card](https://huggingface.co/intfloat/multilingual-e5-small),
[Sentence Transformers embedding](https://www.sbert.net/examples/sentence_transformer/applications/computing-embeddings/README.html),
[pgvector](https://github.com/pgvector/pgvector).

## 5. Хиймэл жишээ: 10 баримт, 20 асуулт

`data/evaluation/smoke/` нь зохиомол номын сангийн Англи баримтууд, Монгол/Англи асуултууд.
Эмнэлгийн зөвлөгөө, дипломын бодит үнэлгээ биш. Зөвхөн тусдаа `thesis_demo` санд ажиллуулна.
Энэ төслийн локал setup-д `thesis_demo`, `thesis_test` үүсгэсэн. Шинэ орчинд root-оос нэг удаа:

```sh
docker compose --env-file .env -f infra/compose.yaml exec db createdb -U thesis thesis_demo
docker compose --env-file .env -f infra/compose.yaml exec db createdb -U thesis thesis_test
```

Дараа нь `backend/` дотроос (`.env`-ийн DB credentials-ийг өөрчилсөн бол URL-аа тохируулна):

```sh
export DATABASE_URL=postgresql+psycopg://thesis:CHANGE_ME@localhost:55432/thesis_demo
uv run alembic upgrade head
uv run --extra embedding python -m app.cli.demo
uv run --extra embedding python -m app.cli search "Номын сан хаалттай үед номоо хаана буцааж өгөх вэ?"
unset DATABASE_URL
```

Demo команд зөвхөн repository-ийн хиймэл fixture-уудыг шалгаж идэвхжүүлнэ.
20 асуултын үр дүн `data/evaluation/results/smoke.json`-д гарна.
Холбогдох chunk-ийг source URL + locator-оор урьдчилан шошголсон; recall@5 нь олдсон зөв chunk-ийн
хувь. Жижиг хиймэл сангийн энэ үзүүлэлтийг бодит RAG чанар гэж тайлагнахгүй.
Өөрийн dataset-ийг ижил JSONL хэлбэрээр бэлдэж `evaluate DATASET --output RESULT.json` хэрэглэнэ.

## 6. Тест ба дараагийн ажил

`backend/` дотроос:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit -q
TEST_DATABASE_URL=postgresql+psycopg://thesis:CHANGE_ME@localhost:55432/thesis_test uv run pytest -q
```

Integration тестүүд `_test`-ээр төгссөн тусдаа сан шаардана, knowledge хүснэгтүүдийг цэвэрлэнэ.
`TEST_DATABASE_URL` байхгүй бол тэд skip болно. Unit/integration тестийн embedding нь fake;
жинхэнэ model-ийн чанарыг demo/evaluation тусад нь шалгана.

Дараагийн шат: бие даасан evaluation асуулт, эмнэлгийн агуулгын хяналт, queue/lease worker.
Хэрэглэгч нэмэх, чат түүхийн заавар frontend/README.md-д бий. Схем: 0002_chat.
# WHO corpus progress

The local WHO starter corpus and Mongolian retrieval pilot are documented in the
[progress report](../report/progress-2026-10-13.md). Reproduce ingestion using the
[WHO corpus instructions](../data/sources/who/README.md).

## Heading-aware retrieval (2026-11-19)

Search now fetches up to 50 active, enabled chunks using content cosine similarity,
then reranks using 70% content cosine + 30% source-title/section-heading cosine.
The final chat context remains top-5. Both embeddings use the pinned local E5 model.
Page/line numbers after `|` are omitted from the heading embedding. Heading vectors
are cached in process memory (up to 2048 entries), keyed by text and embedder instance.
Source title/heading changes generate new cache entries; restart clears the cache.
No database re-embedding or paid API call is required. Cold requests encode headings
and can take longer; this prototype is initially evaluated on 30 chunks (now 37), not large-scale data.

`score` is now a weighted cosine ranking score, not a pure content cosine or probability.
`RETRIEVAL_METADATA_WEIGHT=0` restores the old ranking. `RETRIEVAL_CANDIDATES=50`
controls candidate count (20–200). Restart the backend after environment changes.

Reproduce the comparison from backend/:

```sh
HF_HUB_OFFLINE=1 .venv/bin/python ../scripts/evaluate_retrieval_variants.py \
  ../data/evaluation/who/questions.jsonl \
  --output ../data/evaluation/results/metadata-pilot.json
```

Existing pilot: 45% to 65% recall@5. Supplementary 12 cases: 41.7% to 58.3%.
These are retrieval measures on small author-labelled sets, not clinical answer accuracy.


## 2026-11-20: sentence citations and review

Draft uses `OPENAI_MODEL=gpt-4.1-mini`; supported draft review uses
`OPENAI_REVIEW_MODEL=gpt-4.1` (configurable). Both use Responses, store=false,
45-second request timeouts. A second model call adds cost and latency.
Unsupported/urgent drafts return immediately; over-abstention is a known limitation.
Each supported sentence supplies evidence IDs; the server renders citations and validates them.
Prompt version: mn-grounded-v5-2026-11-20. This does not prove semantic truth.

Corpus: 7 active documents / 37 chunks. The two new sources are explicitly marked
source-checked paraphrases, not verbatim WHO text. See data/sources/who/2026-11-20.
Archived source checksums are verified by scripts/prepare_who_expansion.py before rebuilding.

Final evaluation: paired old evidence 10/10 behavior; fresh 12 cases 9/12.
Three final failures: two over-abstentions and one retrieval miss. Some qualifiers remain incomplete.
Old 20-case retrieval after expansion: 60%, previously 65%. See
[full review](../report/quality-and-corpus-2026-11-20.md). No clinical review performed.


2026-11-26: Нэр, нууц үгийн бүртгэл болон тохиргоотой үед Google нэвтрэлт нэмсэн. [Тохируулах заавар](GOOGLE-LOGIN.md).
