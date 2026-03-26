import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _cors_allow_credentials() -> bool:
    """与 allow_origins 搭配：仅当使用具体来源列表时允许携带凭证（浏览器不接受 * + credentials）。"""
    raw = os.getenv("CORS_ORIGINS", "*").strip()
    return bool(raw and raw != "*")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import uuid
from schemas import (
    ChartRequest,
    SimpleChatRequest,
    SimpleChatResponse,
    UserRegisterRequest,
    PromptUpdateRequest,
    ConversationCreateRequest,
    ConversationOut,
    MessageOut,
)
from app.services.chart_service import calculate_chart
from app.services.chat_service import handle_chat
from app.services.user_service import check_user_exists, register_user
from app.db import init_db, SessionLocal
from app.repositories.user_repo import get_user
from app.repositories import conversation_repo, message_repo
from app.models import SystemPrompt, Conversation

app = FastAPI()

# CORS：默认 * 且不带 credentials；生产可设 CORS_ORIGINS=https://a.com,https://b.com 以启用 credentials
_cors_origins = os.getenv("CORS_ORIGINS", "*").strip() or "*"
_cors_origins_list = (
    ["*"]
    if _cors_origins == "*"
    else [o.strip() for o in _cors_origins.split(",") if o.strip()]
) or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_list,
    allow_credentials=_cors_allow_credentials(),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/calculate-chart")
def calculate(request: ChartRequest):
    return calculate_chart(request)


@app.on_event("startup")
def startup():
    pass  # 数据库初始化已移至 scripts/init_db.py，不在服务启动时自动执行


@app.get("/api/user/check")
def user_check(wechat_id: str):
    exists = check_user_exists(wechat_id)
    return {"exists": exists}


@app.post("/api/user/register")
def user_register(req: UserRegisterRequest):
    try:
        result = register_user(req)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/user/chart")
def user_chart(wechat_id: str):
    """获取已注册用户的星盘信息，供 chat/index 页面展示；含 birth_data 供 index 直接进入星盘解读"""
    db = SessionLocal()
    try:
        user = get_user(db, wechat_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        birth_data = None
        if user.birth_date and user.birth_time:
            birth_data = {
                "date": user.birth_date.isoformat(),
                "time": user.birth_time.strftime("%H:%M"),
                "latitude": user.latitude,
                "longitude": user.longitude,
            }
        return {
            "wechat_id": user.wechat_id,
            "chart_summary": user.chart_summary or "",
            "chart_snapshot": user.chart_snapshot,
            "birth_data": birth_data,
        }
    finally:
        db.close()


@app.get("/api/prompt")
def get_prompt():
    """获取当前 system prompt"""
    db = SessionLocal()
    try:
        row = db.query(SystemPrompt).filter_by(id=1).first()
        if not row:
            raise HTTPException(status_code=404, detail="Prompt not found")
        return {"content": row.content, "updated_at": row.updated_at.isoformat() if row.updated_at else None}
    finally:
        db.close()


@app.put("/api/prompt")
def update_prompt(req: PromptUpdateRequest):
    """更新 system prompt（供非技术人员编辑）"""
    db = SessionLocal()
    try:
        row = db.query(SystemPrompt).filter_by(id=1).first()
        if not row:
            row = SystemPrompt(id=1, content=req.content)
            db.add(row)
        else:
            row.content = req.content
        db.commit()
        db.refresh(row)
        return {"content": row.content, "updated_at": row.updated_at.isoformat() if row.updated_at else None}
    finally:
        db.close()


@app.post("/chat")
def simple_chat(req: SimpleChatRequest) -> SimpleChatResponse:
    try:
        reply, conversation_id, stage = handle_chat(req.wechat_id, req.message, conversation_id=req.conversation_id)
        db = SessionLocal()
        try:
            msg_count = message_repo.count_for_conversation(db, uuid.UUID(conversation_id))
        finally:
            db.close()
        # stage5 之后且会话消息足够长时，提示开启新对话
        # （stage 的业务上限为 5，所以这里等价于 stage == 5）
        suggest_new = stage >= 5 and msg_count > 30
        return SimpleChatResponse(
            answer=reply,
            conversation_id=conversation_id,
            stage=stage,
            suggest_new_conversation=suggest_new,
        )
    except ValueError as e:
        msg = str(e)
        status = 400 if "conversation_id" in msg else 404
        raise HTTPException(status_code=status, detail=msg)

@app.get("/api/conversations")
def list_conversations(wechat_id: str) -> list[ConversationOut]:
    db = SessionLocal()
    try:
        user = get_user(db, wechat_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        convs = conversation_repo.list_for_user(db, user.id)
        return [
            ConversationOut(
                id=str(c.id),
                summary=c.summary,
                created_at=c.created_at.isoformat() if getattr(c, "created_at", None) else None,
                updated_at=c.updated_at.isoformat() if getattr(c, "updated_at", None) else None,
            )
            for c in convs
        ]
    finally:
        db.close()


@app.post("/api/conversations")
def create_conversation(req: ConversationCreateRequest) -> ConversationOut:
    db = SessionLocal()
    try:
        user = get_user(db, req.wechat_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        conv = conversation_repo.create_for_user(db, user.id)

        return ConversationOut(
            id=str(conv.id),
            summary=conv.summary,
            created_at=conv.created_at.isoformat() if getattr(conv, "created_at", None) else None,
            updated_at=conv.updated_at.isoformat() if getattr(conv, "updated_at", None) else None,
        )
    finally:
        db.close()


@app.get("/api/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: str, wechat_id: str) -> list[MessageOut]:
    db = SessionLocal()
    try:
        user = get_user(db, wechat_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="conversation_id 非法")

        conv = conversation_repo.get_for_user(db, conv_uuid, user.id)
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")

        msgs = message_repo.list_all_asc(db, conv.id)
        return [
            MessageOut(
                id=str(m.id),
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat(),
            )
            for m in msgs
        ]
    finally:
        db.close()


# Serve frontend (must be last - catches unmatched routes)
STATIC_DIR = Path(__file__).parent.parent / "frontend"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")