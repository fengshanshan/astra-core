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


def generate_interpretation(prompt: str):
    """
    调用 DeepSeek 生成中文解读
    """

    client = get_llm_client()
    system_prompt = get_system_prompt()

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=800,
    )

    usage = None
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    return {
        "answer": response.choices[0].message.content,
        "usage": usage,
    }


def call_llm(messages: list[dict], chart_context: str | None = None):
    """
    多轮对话模式：messages 为 [{"role": "user"|"assistant", "content": "..."}, ...]
    会与 system prompt 一起传给模型，保持完整对话上下文。
    chart_context: 用户星盘摘要，供模型基于星盘回答；为 None 时表示用户暂无星盘数据。
    """
    client = get_llm_client()
    system_prompt = get_system_prompt()
    if chart_context:
        system_prompt += f"\n\n## 当前用户星盘\n{chart_context}"
    else:
        system_prompt += "\n\n## 当前用户星盘\n用户暂无星盘数据，若问题与星盘相关请礼貌说明无法回答。"
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            *messages,
        ],
        temperature=0.4,
        max_tokens=800,
    )
    return response.choices[0].message.content