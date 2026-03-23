from app.services.llm_service import call_llm
from app.models import Conversation, Message
from app.db import SessionLocal
from app.repositories.user_repo import get_user
from app.services.user_service import build_llm_chart_context
import uuid
from datetime import datetime


MAX_HISTORY = 60


def _advance_stage(conversation: Conversation, message_count: int) -> bool:
    """每 2 轮（4条消息）自动推进一次 stage，最高到 5。返回是否推进了。"""
    if conversation.stage >= 5:
        return False
    if message_count > 0 and message_count % 4 == 0:
        conversation.stage = min(conversation.stage + 1, 5)
        return True
    return False


def update_summary(conversation: Conversation, db) -> None:
    """每隔 6 轮或 stage 推进时，更新对话摘要。"""
    messages_so_far = (
        db.query(Message)
        .filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    formatted = "\n".join(f"{m.role}: {m.content}" for m in messages_so_far)
    new_summary = call_llm(
        messages=[{
            "role": "user",
            "content": f"请将以下对话压缩成一段简短摘要（100字以内），保留：用户的核心困扰、已识别的星象课题、用户说过的关键信息、当前stage。对话内容：{formatted}"
        }],
        chart_context=None,
        stage=None,
        is_summary=True,
    )
    conversation.summary = new_summary
    db.commit()


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
            conversation = Conversation(user_id=user.id)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

        # 统计当前消息数（用于 stage 推进和摘要触发）
        message_count = (
            db.query(Message)
            .filter_by(conversation_id=conversation.id)
            .count()
        )

        # 构建发给 LLM 的消息列表
        messages = []
        if conversation.summary:
            messages.append({
                "role": "system",
                "content": f"【对话摘要】{conversation.summary}"
            })
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

        chart_context = build_llm_chart_context(user)
        assistant_reply = call_llm(messages, chart_context=chart_context, stage=conversation.stage)

        db.add(Message(conversation_id=conversation.id, role="user", content=user_message))
        db.add(Message(conversation_id=conversation.id, role="assistant", content=assistant_reply))
        conversation.updated_at = datetime.utcnow()

        # stage 推进（保存前计数加 2，因为刚加了 user + assistant 两条）
        new_message_count = message_count + 2
        stage_advanced = _advance_stage(conversation, new_message_count)

        db.commit()

        # 触发摘要：每 6 轮（12条）或 stage 推进时
        if stage_advanced or (new_message_count > 0 and new_message_count % 12 == 0):
            update_summary(conversation, db)

        return assistant_reply, str(conversation.id), conversation.stage
    finally:
        db.close()