# Локал нэвтрэлт ба чат

Next.js + Ant Design → FastAPI → WHO retrieval → OpenAI Responses API.
Чат: http://127.0.0.1:3000

Root `.env` дахь `OPENAI_API_KEY`, `OPENAI_MODEL=gpt-4.1-mini`, `OPENAI_REVIEW_MODEL=gpt-4.1` нь зөвхөн backend-д хэрэглэгдэнэ.
Түлхүүрийг `NEXT_PUBLIC` хувьсагчид оруулахгүй. API кредит болон Responses бичих эрх шаардлагатай.

Шинэ хэрэглэгч: `cd backend` дараа `.venv/bin/python ../scripts/manage_users.py create USERNAME`.
Нууц үгийг далд prompt-д хоёр удаа оруулна (12+ тэмдэгт). Бүртгэл давхардахад өөрчлөхгүй.
Хуучин .env хэрэглэгчийг нэг удаа шилжүүлэх: `.venv/bin/python ../scripts/manage_users.py import-local`.

## Ажиллуулах

Root-оос өгөгдлийн сан, backend асаана:

```sh
docker compose --env-file .env -f infra/compose.yaml up -d db
cd backend
uv sync --frozen --extra embedding
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Docker API ба host API хоёрыг 8000 портод зэрэг асаахгүй.
WHO сан бэлтгэх заавар backend/README.md-д бий.

Өөр терминалаас:

```sh
cd frontend
npm ci
npm run build
npm start
```

Хөгжүүлэлтэд `npm run dev` ашиглана. `BACKEND_URL` default: http://127.0.0.1:8000.
Backend `.env` өөрчлөгдвөл backend процессыг дахин асаана.

## Шалгах ба хязгаарлалт

Нэвтрээд асуулт илгээхэд Монгол хариулт, WHO эх сурвалжийн холбоос гарна.
Гарах товч session-ийг хүчингүй болгоно. `npm run typecheck` TypeScript шалгана.
Backend тестийн үр дүн backend/VERIFICATION.md-д бий.

Олон хэрэглэгч, 8 цагийн session, яриа, мессеж болон эшлэлийн snapshot PostgreSQL-д хадгалагдана.
Refresh эсвэл backend restart-ийн дараа “Өмнөх яриа”-аас түүхээ нээнэ. Өөр хэрэглэгчийн ярианд 404 буцаана.
Хэрэглэгч өөрөө бүртгүүлэх болон админ CLI-аар хэрэглэгч нэмэх боломжтой. Нууц үг сэргээх UI байхгүй.
Одоогоор нэг API process ажиллуулна. Амжилттай хариулсан turn-ийг нэг transaction-д хадгална;
алдаатай хүсэлт түүхэд хадгалагдахгүй. Ижил request_id-г дахин илгээвэл хадгалсан хариуг буцаана.
Асуулт бүрийг тусад нь боловсруулна; түүх LLM context-д дамжихгүй.
Асуулт болон олдсон эх хэсгүүд OpenAI-д илгээгдэнэ (`store=false`).
Эшлэлийн дугаар, эх сурвалжийн холбоог шалгана; өгүүлбэр бүрийн утгын үнэн зөвийг
баталгаажуулдаггүй. Эмнэлзүйн чанарын үнэлгээ цааш шаардлагатай.


2026-11-26: Нэр, нууц үгийн бүртгэл болон тохиргоотой үед Google нэвтрэлт нэмсэн. [Тохируулах заавар](../backend/GOOGLE-LOGIN.md).
