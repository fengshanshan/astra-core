from app.knowledge.knowledge_base import KNOWLEDGE_BASE
from app.services.llm_service import call_llm
from app.models import Conversation, Message
from app.db import SessionLocal
from app.repositories.user_repo import get_user

def retrieve_knowledge(features):
    """
    根据 feature 列表匹配知识库内容
    返回匹配到的文本列表
    """

    matched = []
    used_triggers = []

    for feature in features:
        if feature in KNOWLEDGE_BASE:
            matched.append(KNOWLEDGE_BASE[feature]["content"])
            used_triggers.append(feature)

    return matched, used_triggers

MAX_HISTORY = 6

def handle_chat(wechat_id: str, user_message: str):
    db = SessionLocal()
    try:
        user = get_user(db, wechat_id)
        if not user:
            raise ValueError("用户不存在，请先完成用户注册")

        conversation = (
            db.query(Conversation)
            .filter_by(user_id=user.id)
            .first()
        )

        if not conversation:
            conversation = Conversation(user_id=user.id)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

        recent_messages = (
            db.query(Message)
            .filter_by(conversation_id=conversation.id)
            .order_by(Message.created_at.desc())
            .limit(MAX_HISTORY)
            .all()
        )

        messages = []
        for m in reversed(recent_messages):
            messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": user_message})

        chart_context = user.chart_summary
        assistant_reply = call_llm(messages, chart_context=chart_context)

        db.add(Message(conversation_id=conversation.id, role="user", content=user_message))
        db.add(Message(conversation_id=conversation.id, role="assistant", content=assistant_reply))
        db.commit()

        return assistant_reply
    finally:
        db.close()