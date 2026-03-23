import datetime

from app.db import SessionLocal
from app.models import User
from app.repositories.user_repo import get_user
from app.services.chart_service import calculate_chart
from schemas import UserRegisterRequest


def check_user_exists(wechat_id: str) -> bool:
    db = SessionLocal()
    try:
        user = get_user(db, wechat_id)
        return user is not None
    finally:
        db.close()


def register_user(req: UserRegisterRequest) -> dict:
    """Create user with birth profile and chart. Raises if wechat_id already exists."""
    db = SessionLocal()
    try:
        existing = get_user(db, req.wechat_id)
        if existing:
            raise ValueError(f"用户 {req.wechat_id} 已存在")

        # Build chart request for calculate_chart
        from types import SimpleNamespace
        data = SimpleNamespace(
            date=req.date,
            time=req.time,
            latitude=req.latitude,
            longitude=req.longitude,
        )
        chart = calculate_chart(data)

        birth_date = datetime.date.fromisoformat(req.date)
        birth_time = datetime.time.fromisoformat(req.time)

        user = User(
            wechat_id=req.wechat_id,
            birth_date=birth_date,
            birth_time=birth_time,
            latitude=req.latitude,
            longitude=req.longitude,
            chart_snapshot={
                "planets": chart["planets"],
                "ascendant": chart["ascendant"],
                "aspects": chart["aspects"],
            },
            chart_summary=_build_chart_summary(chart, req.place_name),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"user_id": str(user.id), "wechat_id": user.wechat_id}
    finally:
        db.close()


# 星盘表显示顺序
CHART_DISPLAY_ORDER = [
    "sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
    "uranus", "neptune", "pluto",
    "north_node", "south_node", "chiron", "part_of_fortune", "vertex", "juno",
    "ascendant", "descendant", "mc", "ic",
]

CHART_NAME_MAP = {
    "sun": "太阳", "moon": "月亮", "mercury": "水星", "venus": "金星",
    "mars": "火星", "jupiter": "木星", "saturn": "土星",
    "uranus": "天王星", "neptune": "海王星", "pluto": "冥王星",
    "north_node": "北交点", "south_node": "南交点", "chiron": "凯龙星",
    "part_of_fortune": "福点", "vertex": "宿命点", "juno": "婚神星",
    "ascendant": "上升", "descendant": "下降", "mc": "天顶", "ic": "天底",
}


def build_llm_chart_context(user: User) -> str | None:
    """
    供对话 LLM 使用的星盘上下文：优先 chart_summary，缺省时用 chart_snapshot 里的行星表重建；
    并附带已建档的出生信息，避免模型在已有档案时仍索要出生日期/时间/地点。
    """
    blocks: list[str] = []
    meta: list[str] = []
    if user.birth_date:
        meta.append(f"出生日期 {user.birth_date.isoformat()}")
    if user.birth_time:
        meta.append(f"出生时间 {user.birth_time.strftime('%H:%M')}")
    if user.latitude is not None and user.longitude is not None:
        meta.append(f"出生地经纬度 {user.latitude}, {user.longitude}")
    if meta:
        blocks.append(
            "【系统已保存的出生资料（请勿向用户重复索要）】" + "，".join(meta)
        )

    summary = (user.chart_summary or "").strip()
    if not summary and user.chart_snapshot and isinstance(user.chart_snapshot, dict):
        planets = user.chart_snapshot.get("planets")
        if planets:
            summary = _build_chart_summary({"planets": planets}, None)
    if summary:
        blocks.append(summary)

    if not blocks:
        return None
    return "\n\n".join(blocks)


def _build_chart_summary(chart: dict, place_name: str | None) -> str:
    lines = []
    planets = chart.get("planets", {})
    for name in CHART_DISPLAY_ORDER:
        if name not in planets:
            continue
        p = planets[name]
        suffix = ""
        if p.get("stationary") and p.get("retrograde"):
            suffix = " SR"
        elif p.get("stationary"):
            suffix = " S"
        elif p.get("retrograde"):
            suffix = " R"
        label = CHART_NAME_MAP.get(name, name)
        lines.append(f"{label}{suffix}: {p['sign']} {p['degree']}° 第{p['house']}宫")
    if place_name:
        lines.append(f"出生地: {place_name}")
    return "\n".join(lines)
