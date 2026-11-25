from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.chat import router as chat_router
from app.db.session import get_engine
from app.modules.auth.history import router as history_router
from app.modules.auth.google import router as google_router
from app.modules.auth.local import router as auth_router

app = FastAPI(title="Thesis RAG", version="0.3.0")
app.include_router(auth_router)
app.include_router(google_router)
app.include_router(chat_router)
app.include_router(history_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness():
    try:
        with get_engine().connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            connection.execute(text("SELECT '[1,0]'::vector <=> '[1,0]'::vector"))
            if revision != "0003_google":
                return JSONResponse(status_code=503, content={"status": "not_ready"})
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready", "database": "ok", "schema": revision}
