from pathlib import Path
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

def get_system_prompt() -> str:
    """优先从数据库读取，若不存在则从 prompt.md 读取"""
    try:
        from app.db import SessionLocal
        from app.models import SystemPrompt
        db = SessionLocal()
        try:
            row = db.query(SystemPrompt).filter_by(id=1).first()
            if row and row.content:
                return row.content
        finally:
            db.close()
    except Exception:
        pass
    return ""


def get_llm_client():
    return OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com"
    )

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_chart",
            "description": "Calculate natal chart from birth information",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "time": {"type": "string"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"}
                },
                "required": ["date", "time", "latitude", "longitude"]
            }
        }
    }
]


STAGE_INSTRUCTIONS = {
    1: "【当前阶段：第一步】请先基于用户的星象特质，对用户的问题表达理解和共情。不要急于给建议，让用户感到被看见。",
    2: "【当前阶段：第二步】请向用户提问，深入了解问题的具体细节。只问一个最关键的问题。",
    3: "【当前阶段：第三步】请结合用户星盘和刚才了解到的细节，给出初步的占星解读和回应。",
    4: "【当前阶段：第四步】请针对用户在这个课题上的成长方向，提出一个启发性的反问。这个问题应该让用户停下来思考自己。",
    5: "【当前阶段：第五步】请总结这段对话的核心洞察，并给出 1~2 个具体可行的行动建议。",
}


def call_llm(messages: list[dict], chart_context: str | None = None, stage: int | None = None, is_summary: bool = False):
    """
    多轮对话模式：messages 为 [{"role": "user"|"assistant", "content": "..."}, ...]
    会与 system prompt 一起传给模型，保持完整对话上下文。
    chart_context: 用户星盘摘要，供模型基于星盘回答；为 None 时表示用户暂无星盘数据。
    stage: 当前对话阶段（1~5），会在 system prompt 末尾附加对应的阶段指令。
    is_summary: 为 True 时跳过阶段指令和星盘信息，仅用于生成摘要。
    """
    client = get_llm_client()

    if is_summary:
        system_prompt = "你是一个对话摘要助手。"
    else:
        system_prompt = get_system_prompt()
        if chart_context:
            system_prompt += f"\n\n## 当前用户星盘\n{chart_context}"
        else:
            system_prompt += "\n\n## 当前用户星盘\n用户暂无星盘数据，若问题与星盘相关请礼貌说明无法回答。"
        if stage and stage in STAGE_INSTRUCTIONS:
            system_prompt += f"\n\n{STAGE_INSTRUCTIONS[stage]}"

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            *messages,
        ],
        tools=TOOLS if not is_summary else [],
        tool_choice="auto" if not is_summary else "none",
        temperature=0.4,
        max_tokens=8192,
    )
    return response.choices[0].message.content