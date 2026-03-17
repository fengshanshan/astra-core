from app.services.llm_service import call_llm
from app.models import Conversation, Message
from app.db import SessionLocal
from app.repositories.user_repo import get_user
import uuid
from datetime import datetime


MAX_HISTORY = 20

def handle_chat(wechat_id: str, user_message: str, conversation_id: str | None = None):
    db = SessionLocal()
    try:
        user = get_user(db, wechat_id)
        if not user:
            raise ValueError("用户不存在，请先完成用户注册")

        conversation = None
        if conversation_id:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                raise ValueError("conversation_id 非法")
            conversation = (
                db.query(Conversation)
                .filter_by(id=conv_uuid, user_id=user.id)
                .first()
            )

        if not conversation:
            # 未传 conversation_id 视为新会话：创建会话且不带历史
            conversation = Conversation(user_id=user.id)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

        messages = []
        if conversation_id:
            recent_messages = (
                db.query(Message)
                .filter_by(conversation_id=conversation.id)
                .order_by(Message.created_at.desc())
                .limit(MAX_HISTORY)
                .all()
            )
            for m in reversed(recent_messages):
                messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": user_message})

        chart_context = user.chart_summary
        assistant_reply = call_llm(messages, chart_context=chart_context)

        db.add(Message(conversation_id=conversation.id, role="user", content=user_message))
        db.add(Message(conversation_id=conversation.id, role="assistant", content=assistant_reply))
        conversation.updated_at = datetime.utcnow()
        db.commit()

        return assistant_reply, str(conversation.id)
    finally:
        db.close()