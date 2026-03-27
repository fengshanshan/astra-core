import json
import logging
import os
import re
from types import SimpleNamespace

from dotenv import load_dotenv
from openai import OpenAI

from app.services.chart_service import calculate_chart
from app.services.user_service import _build_chart_summary

load_dotenv()

logger = logging.getLogger(__name__)


def get_system_prompt() -> str:
    """从数据库读取 SystemPrompt（id=1）；无有效内容或失败时返回空字符串。"""
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
        logger.exception("从数据库读取 SystemPrompt 失败")
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

_EMPTY_ASSISTANT_FALLBACK = "抱歉，模型暂时未返回有效内容，请稍后再试或换种说法。"
_EMPTY_SUMMARY_FALLBACK = "（摘要暂不可用）"
_TOOL_NUDGE = "请直接用繁体中文回复上一条用户消息，不要调用任何工具，回复不能为空。"
_TOOL_POLICY_FOR_THIRD_PARTY = (
    "## 工具使用规则（严格）\n"
    "当识别到用户在讨论“另一个人”（如妈妈/伴侣/家人）时，本规则优先于阶段指令。\n"
    "你只能在用户明确在讨论“另一个人”且需要星盘判断时，调用 calculate_chart。\n"
    "涉及星盘计算时，必须通过工具计算，禁止凭记忆或心算给出星盘结论。\n"
    "请先友善说明：为了更准确分析，建议提供对方出生日期、出生时间、出生地（或经纬度）。\n"
    "要一次性告诉用户完整所需字段，不要强迫、不施压。\n"
    "若信息不完整，不要调用工具；先基于已知信息给出有限解读，并明确准确度受限。\n"
    "后续仅补问缺失字段，优先级为：日期 > 时间 > 地点（经纬度）。"
)
_STAGE_TAG_PATTERN = re.compile(r"[\[(（]\s*STAGE\s*=\s*(?P<stage>[1-5])\s*[\])）][\s。.!！?？,，;；:：]*$", re.IGNORECASE)


def _normalize_chart_tool_args(args: dict) -> tuple[dict | None, str | None]:
    date = args.get("date")
    time = args.get("time")
    latitude = args.get("latitude")
    longitude = args.get("longitude")

    if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return None, "date 必须是 YYYY-MM-DD 字符串"
    if not isinstance(time, str) or not re.fullmatch(r"\d{2}:\d{2}", time):
        return None, "time 必须是 HH:MM 字符串"

    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None, "latitude/longitude 必须是数字"

    if not (-90 <= lat <= 90):
        return None, "latitude 必须在 -90 到 90 之间"
    if not (-180 <= lon <= 180):
        return None, "longitude 必须在 -180 到 180 之间"

    return {"date": date, "time": time, "latitude": lat, "longitude": lon}, None


def _run_calculate_chart_tool(arguments: str) -> str:
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return json.dumps({"error": "工具参数不是合法 JSON"}, ensure_ascii=False)
    try:
        if not isinstance(args, dict):
            return json.dumps({"error": "工具参数必须是 JSON 对象"}, ensure_ascii=False)
        normalized, err = _normalize_chart_tool_args(args)
        if err:
            return json.dumps({"error": err}, ensure_ascii=False)
        data = SimpleNamespace(
            date=normalized["date"],
            time=normalized["time"],
            latitude=normalized["latitude"],
            longitude=normalized["longitude"],
        )
        chart = calculate_chart(data)
        summary = _build_chart_summary(chart, None)
        return json.dumps({"chart_text": summary}, ensure_ascii=False)
    except Exception:
        logger.exception("执行工具 calculate_chart 失败")
        return json.dumps({"error": "计算星盘失败，请检查输入后重试"}, ensure_ascii=False)


def _tool_result(name: str, arguments: str) -> str:
    if name == "calculate_chart":
        return _run_calculate_chart_tool(arguments)
    return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)


def _tool_result_with_meta(name: str, arguments: str) -> tuple[str, bool]:
    out = _tool_result(name, arguments)
    ok = True
    try:
        parsed = json.loads(out)
        if isinstance(parsed, dict) and parsed.get("error"):
            ok = False
    except Exception:
        ok = False
    return out, ok


def _assistant_api_dict(msg) -> dict:
    row: dict = {"role": "assistant", "content": msg.content}
    tcs = msg.tool_calls or []
    if tcs:
        row["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            }
            for tc in tcs
        ]
    return row


def _extract_stage_tag(text: str) -> tuple[str, int | None]:
    stripped = text.strip()
    m = _STAGE_TAG_PATTERN.search(stripped)
    if not m:
        return stripped, None
    stage_text = m.group("stage")
    cleaned = _STAGE_TAG_PATTERN.sub("", stripped).rstrip()
    return cleaned, int(stage_text)


def call_llm(
    messages: list[dict],
    chart_context: str | None = None,
    stage: int | None = None,
    is_summary: bool = False,
    conversation_summary: str | None = None,
    with_stage_suggestion: bool = False,
    allow_tools: bool = False,
) -> str | tuple[str, int | None]:
    """
    多轮对话模式：messages 为 [{"role": "user"|"assistant", "content": "..."}, ...]
    会与 system prompt 一起传给模型，保持完整对话上下文。
    chart_context: 用户星盘摘要，供模型基于星盘回答；为 None 时表示用户暂无星盘数据。
    stage: 当前对话阶段（1~5），会在 system prompt 末尾附加对应的阶段指令。
    is_summary: 为 True 时跳过阶段指令和星盘信息，仅用于生成摘要。
    conversation_summary: 压缩后的历史摘要，并入单条 system，避免多条 system 消息。
    with_stage_suggestion: True 时在同一次回复中附带下一阶段建议，并返回 (reply, suggested_stage)。
    allow_tools: True 时才允许模型调用工具；默认关闭，避免普通聊天引入不确定性。
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
        if conversation_summary:
            system_prompt += f"\n\n## 对话摘要\n{conversation_summary}"
        if stage and stage in STAGE_INSTRUCTIONS:
            system_prompt += f"\n\n{STAGE_INSTRUCTIONS[stage]}"
        if with_stage_suggestion and stage:
            system_prompt += (
                "\n\n## 阶段建议输出要求\n"
                f"当前阶段是 {stage}。请在正常回复结束后，最后单独一行输出 [STAGE=n]。\n"
                "n 必须是 1~5 的整数，且只能等于当前阶段或当前阶段+1。\n"
                "除这一行外，不要输出任何额外元信息。"
            )
        if allow_tools:
            system_prompt += f"\n\n{_TOOL_POLICY_FOR_THIRD_PARTY}"

    api_messages: list[dict] = [{"role": "system", "content": system_prompt}, *messages]
    use_tools = (not is_summary) and allow_tools
    nudge_used = False
    max_iterations = 8
    tool_call_total = 0
    tool_call_success = 0
    logger.info(
        "llm_call_config is_summary=%s allow_tools=%s use_tools=%s with_stage_suggestion=%s stage=%s message_count=%s",
        is_summary,
        allow_tools,
        use_tools,
        with_stage_suggestion,
        stage,
        len(messages),
    )

    for _ in range(max_iterations):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=api_messages,
                tools=TOOLS if use_tools else [],
                tool_choice="auto" if use_tools else "none",
                temperature=0.4,
                max_tokens=8192,
            )
        except Exception:
            logger.exception("LLM 调用失败")
            return _EMPTY_SUMMARY_FALLBACK if is_summary else _EMPTY_ASSISTANT_FALLBACK
        msg = response.choices[0].message
        tool_calls = list(msg.tool_calls or [])

        if tool_calls:
            tool_call_total += len(tool_calls)
            api_messages.append(_assistant_api_dict(msg))
            for tc in tool_calls:
                out, ok = _tool_result_with_meta(
                    tc.function.name, tc.function.arguments or "{}"
                )
                if ok:
                    tool_call_success += 1
                logger.info(
                    "tool_call name=%s success=%s allow_tools=%s with_stage_suggestion=%s",
                    tc.function.name,
                    ok,
                    allow_tools,
                    with_stage_suggestion,
                )
                api_messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
            continue

        text = (msg.content or "").strip()
        if text:
            if tool_call_total:
                logger.info(
                    "tool_usage_summary total=%s success=%s allow_tools=%s",
                    tool_call_total,
                    tool_call_success,
                    allow_tools,
                )
            if with_stage_suggestion and not is_summary:
                cleaned, suggested_stage = _extract_stage_tag(text)
                return cleaned or _EMPTY_ASSISTANT_FALLBACK, suggested_stage
            return text

        if is_summary:
            return _EMPTY_SUMMARY_FALLBACK
        if not nudge_used:
            nudge_used = True
            nudge = _TOOL_NUDGE
            if with_stage_suggestion and stage:
                nudge += f" 结尾必须单独一行输出 [STAGE=n]，n 只能是 {stage} 或 {min(stage + 1, 5)}。"
            api_messages.append({"role": "user", "content": nudge})
            continue
        return _EMPTY_ASSISTANT_FALLBACK

    return _EMPTY_SUMMARY_FALLBACK if is_summary else _EMPTY_ASSISTANT_FALLBACK