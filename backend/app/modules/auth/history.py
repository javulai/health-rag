import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select

from app.db.session import session_factory
from app.modules.auth.local import current_user
from app.modules.auth.models import Conversation, Message, User

router = APIRouter(prefix="/api/conversations")


def owner(session, username):
    user = session.scalar(select(User).where(User.username == username, User.enabled.is_(True)))
    if not user:
        raise HTTPException(401, "Дахин нэвтэрнэ үү.")
    return user


def owned(session, user, conversation_id):
    conv = session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    if not conv:
        raise HTTPException(404, "Яриа олдсонгүй.")
    return conv


def previous(username, conversation_id, request_id, question):
    with session_factory()() as session:
        user = owner(session, username)
        if conversation_id:
            owned(session, user, conversation_id)
        message = session.scalar(
            select(Message).where(Message.request_id == request_id, Message.role == "user")
        )
        if not message:
            return None
        conv = owned(session, user, message.conversation_id)
        if message.content != question or (conversation_id and conv.id != conversation_id):
            raise HTTPException(409, "Хүсэлтийн ID өөр асуултад ашиглагдсан байна.")
        answer = session.scalar(
            select(Message).where(Message.request_id == request_id, Message.role == "assistant")
        )
        return {
            "conversation_id": str(conv.id),
            "answer": answer.content,
            "sources": answer.sources,
        }


def save_turn(username, conversation_id, request_id, question, result):
    with session_factory().begin() as session:
        user = owner(session, username)
        conv = (
            owned(session, user, conversation_id)
            if conversation_id
            else Conversation(user_id=user.id, title=question[:100])
        )
        session.add(conv)
        session.flush()
        now = time.time()
        conv.updated_at = now
        session.add_all(
            [
                Message(
                    conversation_id=conv.id,
                    request_id=request_id,
                    role="user",
                    content=question,
                    sources=[],
                    created_at=now,
                ),
                Message(
                    conversation_id=conv.id,
                    request_id=request_id,
                    role="assistant",
                    content=result["answer"],
                    sources=result["sources"],
                    created_at=now + 0.000001,
                ),
            ]
        )
        return {**result, "conversation_id": str(conv.id)}


@router.get("")
def conversations(
    response: Response, username: str = Depends(current_user), offset: int = Query(0, ge=0)
):
    response.headers["Cache-Control"] = "no-store"
    with session_factory()() as session:
        user = owner(session, username)
        rows = session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc(), Conversation.id)
            .offset(offset)
            .limit(50)
        ).all()
        return [{"id": str(c.id), "title": c.title, "updated_at": c.updated_at} for c in rows]


@router.get("/{conversation_id}")
def messages(
    conversation_id: UUID,
    response: Response,
    username: str = Depends(current_user),
    offset: int = Query(0, ge=0),
):
    response.headers["Cache-Control"] = "no-store"
    with session_factory()() as session:
        user = owner(session, username)
        conv = owned(session, user, conversation_id)
        rows = session.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at, Message.id)
            .offset(offset)
            .limit(100)
        ).all()
        return {
            "id": str(conv.id),
            "title": conv.title,
            "messages": [
                {"id": str(m.id), "role": m.role, "content": m.content, "sources": m.sources}
                for m in rows
            ],
        }
