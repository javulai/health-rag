# Бүртгэл ба Google нэвтрэлт

Нэвтрэх хуудсын «Бүртгүүлэх» хэсэгт нэр, нууц үг оруулаад шууд чат руу орно. Нэр: 3–50 жижиг латин үсэг, тоо, `_`, `.` эсвэл `-`; нууц үг: 12–256 тэмдэгт. `google_` угтвар нөөцлөгдсөн.

## Google тохиргоо

1. Google Cloud Console → Google Auth Platform-д төсөл сонгож Branding, Audience тохируулна. Testing горимтой бол Test users-д өөрийн Google хаягийг нэмнэ.
2. Clients → Create client → **Web application**.
3. Authorized JavaScript origins-д `http://localhost:3000` болон `http://127.0.0.1:3000` нэмнэ.
4. Төслийн үндсэн `.env` файлд `GOOGLE_CLIENT_ID=...apps.googleusercontent.com` тохируулж backend-ийг дахин асаана.
5. `/login` хуудсыг шинэчлээд Google товчоор нэвтэрнэ. Анх нэвтрэхэд бүртгэл автоматаар үүснэ.

Энэ хэрэгжүүлэлт GIS popup + JavaScript callback ашигладаг. Client secret болон redirect URI шаарддаг authorization-code урсгал биш. Client ID нь нийтэд харагдах тохиргоо; client secret-ийг frontend-д хэзээ ч оруулахгүй.

Backend: `uv sync --extra embedding`, `.venv/bin/alembic upgrade head`, `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`.
Frontend: `npm run build`, `npm run start -- --hostname 127.0.0.1 --port 3000`.

Google-ийн ID token гарын үсэг, audience, issuer, expiration-ийг google-auth шалгана. Nonce cookie-г token-той тулгана; өөрчлөх API-д Origin болон X-Requested-With шалгана. Зөвхөн тогтвортой `sub`-ээр Google бүртгэлийг танина. Ижил имэйлтэй локал бүртгэлтэй автоматаар холбохгүй. Google хэрэглэгчид хэрэглэгчийн нэр санамсаргүй үүснэ. Токеныг чат түүх эсвэл өгөгдлийн санд хадгалахгүй.

Локал бүртгэлд имэйл баталгаажуулалт, нууц үг сэргээх боломж ороогүй. Rate limit нь нэг процессын глобал 10 оролдлого/минут тул олон процессын нийтлэг хамгаалалт биш. Нийтэд байрлуулахад HTTPS болон COOKIE_SECURE=true тохируулна.

Шалгалт: `uv run pytest tests/unit -q`; бодит Google нэвтрэлтийг зөв client ID болон origin тохируулсны дараа шалгана. Автомат тест Google-ийн сүлжээг mock хийдэг.

Албан ёсны баримт:
- https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- https://developers.google.com/identity/gsi/web/reference/js-reference
