# Хүүхдийн эрүүл мэндийн мэдээллийн RAG туслах

WHO эх сурвалжаас холбогдох хэсгийг хайж, монгол хэлээр эшлэлтэй хариулт өгдөг локал судалгааны прототип.

- Next.js, React, Ant Design: бүртгэл, нэвтрэлт, чат, өмнөх ярианы sidebar.
- FastAPI: хэрэглэгчийн эрх, чат API, OpenAI хариулт.
- PostgreSQL + pgvector: хэрэглэгч, чат түүх, баримтын хувилбар, хэсэг болон вектор.
- Локал `intfloat/multilingual-e5-small`: 384 хэмжээст embedding.
- OpenAI: `gpt-4.1-mini` хариулт, `gpt-4.1` нэмэлт хяналт.
- Нэр/нууц үгийн бүртгэл; тохируулсан үед Google нэвтрэлт.

Ерөнхий мэдээлэл өгнө. Онош, эмчилгээг орлохгүй. Асуулт болон хайж олсон эх текст OpenAI руу илгээгдэнэ. Хувийн эмнэлгийн мэдээлэл бүү оруулаарай. Чат түүх хадгалагдах боловч өмнөх мессежүүд дараагийн асуултын LLM контекстэд ордоггүй.

## Шаардлагатай орчин

- Docker Desktop эсвэл OrbStack (ажиллаж байх).
- Python 3.11 эсвэл 3.12, `uv`.
- Node.js 20.9+ болон npm; Node.js 22 LTS ашиглаж болно.
- Интернэт: dependency болон E5 загварыг анх татах, WHO эх татах, OpenAI/Google үйлчилгээнд холбогдох.
- OpenAI API түлхүүр, тухайн загваруудыг ашиглах эрх ба API үлдэгдэл.

## 1. Код татах

```sh
git clone git@github.com:javulai/health-rag.git
cd health-rag
cp .env.example .env
```

`.env` өмнө байгаа бол хуулж дарж бичихгүй. Жинхэнэ түлхүүр, нууц үгийг зөвхөн локал `.env`-д тохируулна. Энэ файл Git-д орохгүй.

`.env` дотор:

- `OPENAI_API_KEY`: өөрийн OpenAI түлхүүр.
- `POSTGRES_PASSWORD`: өөрийн сонгосон локал сангийн нууц үг.
- `DATABASE_URL`: дээрх нууц үгтэй ижил утгатай PostgreSQL URL. Тусгай тэмдэгттэй нууц үгийг URL-encode хийнэ.
- `GOOGLE_CLIENT_ID`: Google нэвтрэлт ашиглах бол тохируулна; хэрэглэхгүй бол хоосон үлдээнэ.

`.env.example` нь зөвхөн загвар. Түлхүүрийг `NEXT_PUBLIC_` хувьсагчид хийж болохгүй. `.env` өөрчилсний дараа backend-ийг дахин асаана.

## 2. PostgreSQL асаах

Төслийн үндсэн хавтаснаас:

```sh
docker compose --env-file .env -f infra/compose.yaml up -d db
```

Сан `127.0.0.1:55432` дээр ажиллана. Өгөгдөл Docker volume-д хадгалагдана. Шинэ сан эхлээд хэрэглэгч, WHO өгөгдөлгүй байна.

## 3. Backend асаах

Эхний терминалд:

```sh
cd backend
uv sync --frozen --extra embedding
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

- API баримт: http://127.0.0.1:8000/docs
- Процесс: http://127.0.0.1:8000/health
- Сан, схем: http://127.0.0.1:8000/health/ready

`ready` төлөв нь model татагдсан, WHO сан бэлэн, OpenAI түлхүүр хүчинтэйг батлахгүй. E5 загвар анхны ingest/search үед татагдаж `data/models/` дотор хадгалагдана.

## 4. Frontend асаах

Хоёр дахь терминалд төслийн үндсэн хавтаснаас:

```sh
cd frontend
npm ci
npm run build
npm start
```

http://127.0.0.1:3000/login руу орж **Бүртгүүлэх** хэсгээс хэрэглэгч үүсгэнэ. Нэр: 3–50 жижиг латин үсэг, тоо, `_`, `.` эсвэл `-`; нууц үг: 12–256 тэмдэгт. Амжилттай бүртгүүлсний дараа чат нээгдэнэ.

Хөгжүүлэлтийн үед `npm start`-ийн оронд `npm run dev` ашиглана. Next.js proxy нь анхдагчаар `http://127.0.0.1:8000` backend рүү холбогдоно. Өөр хаяг хэрэглэх бол frontend build хийхдээ `BACKEND_URL` тохируулна.

## 5. WHO мэдлэгийн сан бэлтгэх

Repository нь бэлэн database, эх PDF, model cache, хэрэглэгчийн түүх агуулахгүй. Код татаж ажиллуулсан нь мэдлэгийн санг автоматаар бөглөхгүй.

WHO эхний багцын каталог `data/sources/who/catalog.json` дотор бий. Төслийн үндсэн хавтаснаас:

```sh
backend/.venv/bin/python scripts/who_corpus.py fetch
backend/.venv/bin/python scripts/who_corpus.py prepare
backend/.venv/bin/python scripts/who_corpus.py ingest
```

Энэ нь эх татах, сонгосон текст бэлтгэх, staging хувилбар оруулах дараалал. Алсын файл өөрчлөгдсөн эсвэл checksum зөрсөн бол эхийг шалгаж байж үргэлжлүүлнэ. Шинэ хувилбар шууд хайлтад ашиглагдахгүй.

Ingest-ийн үр дүнд гарсан `version_id` бүрийг шалгаад идэвхжүүлнэ. Доорх `VERSION_UUID`, `REVIEWER`-ийг өөрийн утгаар солино:

```sh
cd backend
uv run python -m app.cli inspect VERSION_UUID
uv run python -m app.cli activate VERSION_UUID --reviewer REVIEWER
uv run python -m app.cli search 'Нэмэгдэл хоолыг хэдэн сартайгаас эхлүүлэх вэ?'
```

Шалгах зүйл: эх текст, нас, тоо, нөхцөл, хуудас/хэсгийн locator, ашиглах эрх. Reviewer тэмдэглэгээ нь эмнэлзүйн баталгаа биш. Өөр PDF/Markdown оруулах дэлгэрэнгүйг [backend заавар](backend/README.md)-аас үзнэ. Текстгүй зурагт PDF-д OCR урьдчилан шаардлагатай.

## 6. Google нэвтрэлт (сонголт)

Google Cloud-д Web application төрлийн client үүсгэж Authorized JavaScript origins-д `http://localhost:3000`, `http://127.0.0.1:3000` хаягийг нэмнэ. Consent/Audience тохиргоогоо дуусгана. Testing горим шаардвал Test users нэмнэ.

`.env` дотор `GOOGLE_CLIENT_ID` тохируулаад backend-ийг дахин асаана. Энэ GIS popup хувилбарт client secret шаардлагагүй. Тохиргоогүй үед Google товч харагдахгүй. [Дэлгэрэнгүй](backend/GOOGLE-LOGIN.md).

## Тест ажиллуулах

```sh
cd backend
uv run pytest tests/unit -q
```

PostgreSQL integration тестэд **зөвхөн тусдаа, `_test`-ээр төгссөн сан** ашиглана. Тест тухайн сангийн өгөгдлийг цэвэрлэдэг. `TEST_DATABASE_URL`-ийг түр орчны хувьсагчаар тохируулаад:

```sh
uv run pytest tests/integration -q
```

Frontend шалгалт:

```sh
cd frontend
npm run build
```

## Зогсоох, дахин асаах

Backend болон frontend терминалд `Ctrl+C`. Төслийн үндсэн хавтаснаас санг зогсоох:

```sh
docker compose --env-file .env -f infra/compose.yaml stop db
```

Дахин асаахад сангийн `up -d db`, backend болон frontend асаах командуудыг ажиллуулна. `down -v` нь Docker volume болон өгөгдлийг устгадаг.

## Түгээмэл алдаа

- **Санд холбогдохгүй:** Docker ажиллаж байгаа эсэх, 55432 порт, `.env` дахь нууц үг болон DATABASE_URL-ийг шалгана. Хуучин volume-ийн нууц үг `.env` өөрчлөхөд автоматаар солигдохгүй.
- **Хариулах эх олдохгүй:** staging хувилбараа inspect хийж activate болгосон эсэхийг шалгана.
- **OpenAI 401/429:** түлхүүр, API эрх, хэрэглээний үлдэгдэл/хязгаарыг шалгана; түлхүүр соливол backend дахин асаана.
- **Google origin алдаа:** хөтчийн scheme, host, port нь Google Cloud тохиргоотой яг таарах ёстой.
- **Хэт олон оролдлого:** нэвтрэлт/бүртгэлд нэг процессын 10 оролдлого/минут хязгаар бий.

## Хавтасны бүтэц

```text
backend/          FastAPI, RAG, database model, migrations, tests
frontend/         Next.js + Ant Design интерфэйс
infra/            Docker Compose ба PostgreSQL
scripts/          WHO өгөгдөл бэлтгэл, хэрэглэгч, үнэлгээ
 data/sources/    Эх сурвалжийн каталог, metadata
 data/evaluation/ Туршилтын асуулт, зохиомол smoke өгөгдөл
```

Нэг backend process-той локал прототип. Хүсэлтийн queue/polling, нууц үг сэргээх, чат устгах UI хэрэгжээгүй. Нийтэд байрлуулахад HTTPS, secure cookie, нөөцлөлт болон олон процессын хамгаалалтыг тусад нь шийднэ.
