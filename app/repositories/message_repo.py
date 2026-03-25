import uuid

from sqlalchemy.orm import Session

from app.models import Message


def count_for_conversation(db: Session, conversation_id: uuid.UUID) -> int:
    return db.query(Message).filter_by(conversation_id=conversation_id).count()


def list_recent_desc(db: Session, conversation_id: uuid.UUID, limit: int) -> list[Message]:
    return (
        db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )


def list_all_asc(db: Session, conversation_id: uuid.UUID) -> list[Message]:
    return (
        db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )


def add_exchange(
    db: Session,
    conversation_id: uuid.UUID,
    user_content: str,
    assistant_content: str,
) -> None:
    db.add(Message(conversation_id=conversation_id, role="user", content=user_content))
    db.add(Message(conversation_id=conversation_id, role="assistant", content=assistant_content))
