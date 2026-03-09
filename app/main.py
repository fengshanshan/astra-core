from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fastapi import HTTPException
from fastapi.responses import RedirectResponse

from schemas import ChartRequest, ChatRequest, SimpleChatRequest, UserRegisterRequest, PromptUpdateRequest
from app.services.chart_service import calculate_chart
from app.services.chat_service import retrieve_knowledge, handle_chat
from app.services.llm_service import generate_interpretation
from app.services.user_service import check_user_exists, register_user
from app.db import init_db, SessionLocal
from app.repositories.user_repo import get_user
from app.models import SystemPrompt

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
    return {"status": "chart service running"}


@app.post("/api/calculate-chart")
def calculate(request: ChartRequest):
    return calculate_chart(request)


def build_chat_prompt(chart, matched_texts, user_question):

    knowledge_section = "\n".join(matched_texts)

    return f"""
【星盘数据】
{chart}

【已匹配因素】
{knowledge_section}

【用户问题】
{user_question}

请基于星盘回答用户问题。
"""


@app.post("/api/chat")
def chat(request: ChatRequest):

    # 1. 计算星盘
    result = calculate_chart(request)

    planets = result["planets"]
    ascendant = result["ascendant"]
    aspects = result["aspects"]
    features = result["features"]

    # 2️⃣ 构造 chart_data（用于 prompt）
    chart_data = {"planets": planets, "ascendant": ascendant, "aspects": aspects}

    # 3️⃣ RAG：匹配知识块
    matched_texts, used_triggers = retrieve_knowledge(features)

    # 4️⃣ 构建 userprompt
    prompt = build_chat_prompt(
        chart=chart_data, matched_texts=matched_texts, user_question=request.question
    )

    # 5️⃣ 调用 DeepSeek
    result = generate_interpretation(prompt)

    return {
        "answer": result["answer"],
        "usage": result["usage"],
        "triggers_used": used_triggers,
        "chart": chart_data,
    }


@app.on_event("startup")
def startup():
    try:
        init_db()
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(
            "Database init failed (chart features will work; /chat requires DB): %s", e
        )


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
def simple_chat(req: SimpleChatRequest):
    try:
        reply = handle_chat(req.wechat_id, req.message)
        return {"answer": reply}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/chat.html")
def redirect_chat():
    """chat.html 已合并为首页，重定向到 /"""
    return RedirectResponse(url="/", status_code=301)

# Serve frontend (must be last - catches unmatched routes)
STATIC_DIR = Path(__file__).parent.parent / "frontend"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")