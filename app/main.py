from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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
from app.models import SystemPrompt, Conversation, Message

app = FastAPI()

# CORS for frontend (e.g. when served from different origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
            from app.models import Message as Msg
            import uuid as _uuid
            msg_count = db.query(Msg).filter_by(conversation_id=_uuid.UUID(conversation_id)).count()
        finally:
            db.close()
        suggest_new = stage == 5 or msg_count > 24
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

        convs = (
            db.query(Conversation)
            .filter_by(user_id=user.id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )
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

        conv = Conversation(user_id=user.id)
        db.add(conv)
        db.commit()
        db.refresh(conv)

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

        conv = (
            db.query(Conversation)
            .filter_by(id=conv_uuid, user_id=user.id)
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")

        msgs = (
            db.query(Message)
            .filter_by(conversation_id=conv.id)
            .order_by(Message.created_at.asc())
            .all()
        )
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