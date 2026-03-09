from sqlalchemy.orm import Session

from app.models import User


def get_user(db: Session, wechat_id: str) -> User | None:
    return db.query(User).filter_by(wechat_id=wechat_id).first()


def get_or_create_user(db: Session, wechat_id: str) -> User:
    user = db.query(User).filter_by(wechat_id=wechat_id).first()
    if user:
        return user

    user = User(wechat_id=wechat_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user