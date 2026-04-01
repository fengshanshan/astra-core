"""高德地图 Web 服务：地点提示（中文/拼音模糊）、逆地理编码。GCJ-02 与 WGS84 互转供星历计算使用 WGS84。"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# 高德 Web 服务 Key（控制台：https://console.amap.com/）
AMAP_KEY_ENV = "AMAP_KEY"
# 默认直连公网（忽略 HTTP_PROXY/HTTPS_PROXY）。若必须通过公司代理出网，设为 1/true。
GEO_USE_SYSTEM_PROXY_ENV = "GEO_USE_SYSTEM_PROXY"


def _in_china(lat: float, lon: float) -> bool:
    return 0.83 <= lat <= 55.83 and 72.0 <= lon <= 137.84


def _gcj_offset_from_wgs(lat: float, lon: float) -> tuple[float, float]:
    """在 WGS84 经纬度处，GCJ 相对 WGS 的偏移 (dlat, dlon)。"""
    a = 6378245.0
    ee = 0.00669342162296594323
    dlat = _transform_lat(lon - 105.0, lat - 35.0)
    dlon = _transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = 1.0 - ee * math.sin(radlat) ** 2
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return dlat, dlon


def wgs84_to_gcj02(lat: float, lon: float) -> tuple[float, float]:
    """WGS84 → GCJ-02（国测局），境外不变。"""
    if not _in_china(lat, lon):
        return lat, lon
    dlat, dlon = _gcj_offset_from_wgs(lat, lon)
    return lat + dlat, lon + dlon


def gcj02_to_wgs84(lat: float, lon: float) -> tuple[float, float]:
    """GCJ-02 → WGS84（近似逆变换，与常见 eviltransform 一致），境外不变。"""
    if not _in_china(lat, lon):
        return lat, lon
    dlat, dlon = _gcj_offset_from_wgs(lat, lon)
    return lat - dlat, lon - dlon


def _transform_lat(x: float, y: float) -> float:
    ret = (
        -100.0
        + 2.0 * x
        + 3.0 * y
        + 0.2 * y * y
        + 0.1 * x * y
        + 0.2 * math.sqrt(abs(x))
    )
    ret += (
        (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    )
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x: float, y: float) -> float:
    ret = (
        300.0
        + x
        + 2.0 * y
        + 0.1 * x * x
        + 0.1 * x * y
        + 0.1 * math.sqrt(abs(x))
    )
    ret += (
        (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    )
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def _use_system_proxy_for_http() -> bool:
    return os.getenv(GEO_USE_SYSTEM_PROXY_ENV, "").strip().lower() in ("1", "true", "yes")


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    """
    urllib 会读取 HTTP(S)_PROXY；若指向 127.0.0.1:端口而代理未启动，会出现 Errno 61 Connection refused。
    默认用 ProxyHandler({}) 直连高德；需走系统代理时设置 GEO_USE_SYSTEM_PROXY=1。
    """
    req = urllib.request.Request(url, headers=headers or {})
    if _use_system_proxy_for_http():
        opener = urllib.request.build_opener()
    else:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=12) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        errno = getattr(reason, "errno", None) if isinstance(reason, OSError) else None
        hint = ""
        if errno == 61 or "Connection refused" in str(reason):
            hint = (
                "（连接被拒绝：若已设置 GEO_USE_SYSTEM_PROXY=1，请检查代理是否可用；"
                "否则请检查本机/服务器出网与防火墙。）"
            )
        raise OSError(f"{reason}{hint}") from e


def amap_configured() -> bool:
    return bool(os.getenv(AMAP_KEY_ENV, "").strip())


def _geocode_level_rank(level: str | None) -> int:
    """数值越小越像「整片行政区」，优先于门牌/兴趣点（更接近用户说的「某城市默认点」）。"""
    if not level or not isinstance(level, str):
        return 50
    order = (
        "国家",
        "省",
        "市",
        "区县",
        "区",
        "县",
        "乡镇",
        "街道",
        "门牌",
        "门牌号",
        "兴趣点",
    )
    for i, key in enumerate(order):
        if key in level:
            return i
    return 40


def _dedup_geo_results(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    seen: set[tuple[float, float]] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        lat, lng = r["lat"], r["lng"]
        k = (round(lat, 4), round(lng, 4))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
        if len(out) >= limit:
            break
    return out


def _amap_geocode_geo(key: str, address: str) -> list[dict[str, Any]]:
    """地理编码：对「北京」「上海市」等通常返回市/区级代表坐标，更接近行政中心，而非某条联想 POI。"""
    q = urllib.parse.urlencode({"key": key, "address": address[:100]})
    url = f"https://restapi.amap.com/v3/geocode/geo?{q}"
    data = _http_get_json(url)
    if str(data.get("status")) != "1":
        return []
    geocodes = data.get("geocodes") or []
    parsed: list[tuple[int, dict[str, Any]]] = []
    for g in geocodes:
        if not isinstance(g, dict):
            continue
        loc = g.get("location")
        if not loc or not isinstance(loc, str):
            continue
        parts = loc.split(",")
        if len(parts) != 2:
            continue
        try:
            gcj_lon = float(parts[0].strip())
            gcj_lat = float(parts[1].strip())
        except ValueError:
            continue
        w_lat, w_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)
        formatted = (g.get("formatted_address") or "").strip() or address
        level = g.get("level")
        rank = _geocode_level_rank(level if isinstance(level, str) else None)
        parsed.append(
            (
                rank,
                {
                    "name": formatted,
                    "lat": w_lat,
                    "lng": w_lon,
                },
            )
        )
    parsed.sort(key=lambda x: x[0])
    return [item[1] for item in parsed[:5]]


def _amap_inputtips(key: str, keywords: str) -> list[dict[str, Any]]:
    """inputtips：中文、拼音、简拼模糊联想（首条常为热门 POI，不一定在市中心）。"""
    q = urllib.parse.urlencode(
        {
            "key": key,
            "keywords": keywords[:100],
            "type": "",
            "city": "",
            "citylimit": "false",
        }
    )
    url = f"https://restapi.amap.com/v3/assistant/inputtips?{q}"
    data = _http_get_json(url)
    if str(data.get("status")) != "1":
        return []
    tips = data.get("tips") or []
    out: list[dict[str, Any]] = []
    for t in tips:
        if not isinstance(t, dict):
            continue
        loc = t.get("location")
        if not loc or not isinstance(loc, str):
            continue
        parts = loc.split(",")
        if len(parts) != 2:
            continue
        try:
            gcj_lon = float(parts[0].strip())
            gcj_lat = float(parts[1].strip())
        except ValueError:
            continue
        w_lat, w_lon = gcj02_to_wgs84(gcj_lat, gcj_lon)
        name = (t.get("name") or "").strip()
        district = (t.get("district") or "").strip()
        addr = (t.get("address") or "").strip()
        if district and name and district not in name:
            display = f"{district} · {name}"
        elif addr and name:
            display = f"{name} ({addr})"
        else:
            display = name or addr or district or "地点"
        out.append(
            {
                "name": display,
                "lat": w_lat,
                "lng": w_lon,
            }
        )
    return out


def search_places_amap(key: str, keywords: str, *, city_only: bool = False) -> list[dict[str, Any]]:
    """先地理编码（行政区代表点），再合并输入提示。
    city_only：优先仅用 geocode（国内城市代表点）；若无结果则回退 inputtips，以支持国际城市等。
    """
    geo = _amap_geocode_geo(key, keywords)
    tips = _amap_inputtips(key, keywords)
    if city_only:
        if geo:
            return _dedup_geo_results(geo, limit=8)
        return _dedup_geo_results(tips, limit=8)
    merged = geo + tips
    return _dedup_geo_results(merged, limit=8)


def reverse_geocode_amap(key: str, lat_wgs84: float, lon_wgs84: float) -> str:
    gcj_lat, gcj_lon = wgs84_to_gcj02(lat_wgs84, lon_wgs84)
    loc = f"{gcj_lon},{gcj_lat}"
    q = urllib.parse.urlencode({"key": key, "location": loc})
    url = f"https://restapi.amap.com/v3/geocode/regeo?{q}"
    data = _http_get_json(url)
    if str(data.get("status")) != "1":
        return f"{lat_wgs84:.4f}°, {lon_wgs84:.4f}°"
    regeo = data.get("regeocode") or {}
    formatted = (regeo.get("formatted_address") or "").strip()
    if formatted:
        return formatted
    return f"{lat_wgs84:.4f}°, {lon_wgs84:.4f}°"


def search_places(keywords: str, *, city_only: bool = False) -> tuple[str, list[dict[str, Any]]]:
    """返回 (provider, results)。无 AMAP_KEY 时 provider 为 none、results 为空。"""
    kw = keywords.strip()
    if not kw:
        return "none", []
    key = os.getenv(AMAP_KEY_ENV, "").strip()
    if not key:
        return "none", []
    return "amap", search_places_amap(key, kw, city_only=city_only)


def reverse_geocode(lat: float, lon: float) -> tuple[str, str]:
    """无 Key 时返回坐标字符串。"""
    key = os.getenv(AMAP_KEY_ENV, "").strip()
    if not key:
        return "none", f"{lat:.4f}°, {lon:.4f}°"
    return "amap", reverse_geocode_amap(key, lat, lon)
