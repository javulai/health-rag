import threading
from functools import lru_cache
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import session_factory
from app.modules.auth.history import previous, save_turn
from app.modules.auth.local import csrf, current_user
from app.rag.embeddings import E5Embedder
from app.rag.generation import generate
from app.rag.retrieval import search

router = APIRouter(prefix="/api")
gate = threading.BoundedSemaphore(1)


@lru_cache
def embedder():
    return E5Embedder(get_settings())


class Question(BaseModel):
    conversation_id: UUID | None = None
    request_id: UUID = Field(default_factory=uuid4)
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value.strip()


@router.post("/chat", dependencies=[Depends(csrf)])
def chat(body: Question, response: Response, username: str = Depends(current_user)):
    settings = get_settings()
    if not settings.openai_api_key.get_secret_value():
        raise HTTPException(503, "OpenAI API түлхүүр тохируулаагүй байна.")
    if not gate.acquire(blocking=False):
        raise HTTPException(429, "Өмнөх хүсэлт боловсруулагдаж байна. Түр хүлээгээд оролдоно уу.")
    try:
        cached = previous(username, body.conversation_id, body.request_id, body.question)
        if cached:
            response.headers["Cache-Control"] = "no-store"
            return cached
        sources = search(session_factory(), embedder(), body.question, 5)
        result = generate(settings, body.question, sources)
        response.headers["Cache-Control"] = "no-store"
        return save_turn(username, body.conversation_id, body.request_id, body.question, result)
    except httpx.TimeoutException:
        raise HTTPException(504, "Хариулт удаж байна. Дахин оролдоно уу.") from None
    except httpx.HTTPStatusError as exc:
        message = "OpenAI үйлчилгээ хүсэлтийг хүлээж авсангүй."
        if exc.response.status_code in (401, 403):
            message = "OpenAI түлхүүр эсвэл Responses Write эрхийг шалгана уу."
        elif exc.response.status_code == 429:
            message = "OpenAI хэрэглээний хязгаар эсвэл үлдэгдлийг шалгана уу."
            try:
                code = exc.response.json().get("error", {}).get("code")
            except ValueError:
                code = None
            if code in {"credit_balance_exhausted", "insufficient_quota"}:
                message = (
                    "OpenAI API кредит дууссан байна. "
                    "Billing хэсэгт кредит нэмээд дахин оролдоно уу."
                )
        raise HTTPException(502, message) from None
    except (httpx.RequestError, SQLAlchemyError, OSError):
        raise HTTPException(503, "Хариултын үйлчилгээтэй холбогдож чадсангүй.") from None
    except ValueError:
        raise HTTPException(
            422,
            "Асуултыг богиносгон дахин оролдоно уу. "
            "Хариулт эсвэл эх сурвалжийн шалгалт амжилтгүй боллоо.",
        ) from None
    finally:
        gate.release()
