import uuid

from sqlalchemy.orm import Session

from app.models import Conversation


def get_for_user(db: Session, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
    return (
        db.query(Conversation)
        .filter_by(id=conversation_id, user_id=user_id)
        .first()
    )


def list_for_user(db: Session, user_id: uuid.UUID) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter_by(user_id=user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def create_for_user(db: Session, user_id: uuid.UUID) -> Conversation:
    conv = Conversation(user_id=user_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv
