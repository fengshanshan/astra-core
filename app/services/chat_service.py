import uuid
from datetime import datetime, timezone
import logging

from app.db import SessionLocal
from app.models import Conversation
from app.repositories import conversation_repo, message_repo
from app.repositories.user_repo import get_user
from app.services.llm_service import call_llm
from app.services.user_service import build_llm_chart_context


MAX_HISTORY = 60
logger = logging.getLogger(__name__)


def _advance_stage(conversation: Conversation, message_count: int) -> bool:
    """每 2 轮（4条消息）自动推进一次 stage，最高到 5。返回是否推进了。"""
    if conversation.stage >= 5:
        return False
    if message_count > 0 and message_count % 4 == 0:
        conversation.stage = min(conversation.stage + 1, 5)
        return True
    return False


def _apply_model_stage(
    conversation: Conversation, suggested_stage: int | None, message_count: int
) -> bool:
    """
    优先采用模型建议，但保持可控：
    - 只允许保持不变或 +1
    - 不允许回退和跨级
    - 非法建议时回退到既有规则
    """
    current = conversation.stage
    if suggested_stage in (current, min(current + 1, 5)):
        conversation.stage = suggested_stage
        return suggested_stage > current
    return _advance_stage(conversation, message_count)


def update_summary(conversation_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """每隔 6 轮或 stage 推进时，更新对话摘要。LLM 调用前后不占用同一数据库会话。"""
    db = SessionLocal()
    try:
        conv = conversation_repo.get_for_user(db, conversation_id, user_id)
        if not conv:
            return
        messages_so_far = message_repo.list_all_asc(db, conversation_id)
        formatted = "\n".join(f"{m.role}: {m.content}" for m in messages_so_far)
    finally:
        db.close()

    new_summary = call_llm(
        messages=[{
            "role": "user",
            "content": (
                "请将以下对话压缩成一段简短摘要（100字以内），保留：用户的核心困扰、"
                "已识别的星象课题、用户说过的关键信息、当前stage。对话内容："
                f"{formatted}"
            ),
        }],
        chart_context=None,
        stage=None,
        is_summary=True,
    )

    db = SessionLocal()
    try:
        conv = conversation_repo.get_for_user(db, conversation_id, user_id)
        if conv:
            conv.summary = new_summary
            db.commit()
    finally:
        db.close()


def handle_chat(wechat_id: str, user_message: str, conversation_id: str | None = None):
    conv_uuid: uuid.UUID | None = None
    message_count = 0
    summary_text: str | None = None
    history: list[dict] = []
    chart_context: str | None = None
    stage = 1

    db = SessionLocal()
    try:
        user = get_user(db, wechat_id)
        if not user:
            raise ValueError("用户不存在，请先完成用户注册")

        conversation = None
        if conversation_id:
            try:
                cid = uuid.UUID(conversation_id)
            except ValueError:
                raise ValueError("conversation_id 非法")
            conversation = conversation_repo.get_for_user(db, cid, user.id)

        if not conversation:
            conversation = conversation_repo.create_for_user(db, user.id)

        conv_uuid = conversation.id
        message_count = message_repo.count_for_conversation(db, conversation.id)
        s = (conversation.summary or "").strip()
        summary_text = s if s else None

        if conversation_id:
            recent_messages = message_repo.list_recent_desc(
                db, conversation.id, MAX_HISTORY
            )
            for m in reversed(recent_messages):
                history.append({"role": m.role, "content": m.content})

        chart_context = build_llm_chart_context(user)
        stage = conversation.stage
    finally:
        db.close()

    messages: list[dict] = [*history, {"role": "user", "content": user_message}]

    assistant_reply, suggested_stage = call_llm(
        messages,
        chart_context=chart_context,
        stage=stage,
        conversation_summary=summary_text,
        with_stage_suggestion=True,
    )

    db = SessionLocal()
    try:
        user = get_user(db, wechat_id)
        if not user:
            raise ValueError("用户不存在，请先完成用户注册")
        if conv_uuid is None:
            raise ValueError("会话不存在")

        conversation = conversation_repo.get_for_user(db, conv_uuid, user.id)
        if not conversation:
            raise ValueError("会话不存在")

        message_repo.add_exchange(
            db, conversation.id, user_message, assistant_reply
        )
        conversation.updated_at = datetime.now(timezone.utc)

        new_message_count = message_count + 2
        current_stage = conversation.stage
        stage_advanced = _apply_model_stage(
            conversation, suggested_stage, new_message_count
        )
        logger.info(
            "stage_decision conversation_id=%s current=%s suggested=%s applied=%s advanced=%s",
            conversation.id,
            current_stage,
            suggested_stage,
            conversation.stage,
            stage_advanced,
        )

        db.commit()

        if stage_advanced or (new_message_count > 0 and new_message_count % 12 == 0):
            update_summary(conversation.id, user.id)

        return assistant_reply, str(conversation.id), conversation.stage
    finally:
        db.close()
