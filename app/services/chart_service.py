import swisseph as swe
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from timezonefinder import TimezoneFinder

from zodiac import longitude_to_sign

# Ephemeris data path (project root / ephemeris)
EPHE_PATH = Path(__file__).parent.parent.parent / "ephemeris"
swe.set_ephe_path(str(EPHE_PATH))

tf = TimezoneFinder()

PLANETS = {
    "sun": swe.SUN,
    "moon": swe.MOON,
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
}

ASPECTS = {
    "conjunction": 0,
    "sextile": 60,
    "square": 90,
    "trine": 120,
    "opposition": 180,
}

ORB = 8  # 你设置为 8


# 中国时区，未传经纬度时使用
DEFAULT_TZ = "Asia/Shanghai"
# 北京坐标，未传经纬度时用于宫位计算
DEFAULT_LAT, DEFAULT_LON = 39.9, 116.4

tf = TimezoneFinder()


def local_to_utc(date_str, time_str, lat, lon):
    """
    date_str: "1992-04-03"
    time_str: "15:05"
    lat, lon: float
    """

    # 1️⃣ 根据经纬度查找 timezone 名称
    timezone_name = tf.timezone_at(lat=lat, lng=lon)

    if timezone_name is None:
        raise ValueError("无法根据经纬度确定时区")

    # 2️⃣ 构造本地 datetime
    local_dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

    # 3️⃣ 绑定 timezone（自动处理 DST）
    local_dt = local_dt.replace(tzinfo=ZoneInfo(timezone_name))

    # 4️⃣ 转换为 UTC
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

    return utc_dt


def calculate_aspects(planet_longitudes):
    aspects_found = []
    names = list(planet_longitudes.keys())

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            p1 = names[i]
            p2 = names[j]

            lon1 = planet_longitudes[p1]
            lon2 = planet_longitudes[p2]

            diff = abs(lon1 - lon2)
            diff = min(diff, 360 - diff)

            for aspect_name, angle in ASPECTS.items():
                if abs(diff - angle) <= ORB:
                    aspects_found.append(
                        {
                            "between": [p1, p2],
                            "type": aspect_name,
                            "orb": round(abs(diff - angle), 2),
                        }
                    )

    return aspects_found


def get_house_number(longitude, house_cusps):
    """
    longitude: 0~360
    house_cusps: swe.houses()[0] 返回的 1-based cusp 数组
    """

    for i in range(1, 13):
        start = house_cusps[i]
        end = house_cusps[i + 1] if i < 12 else house_cusps[1]

        if start < end:
            if start <= longitude < end:
                return i
        else:
            # 跨 360°
            if longitude >= start or longitude < end:
                return i

    return None


def calculate_chart(data):
    lat = data.latitude if data.latitude is not None else DEFAULT_LAT
    lon = data.longitude if data.longitude is not None else DEFAULT_LON

    # 1️⃣ 转 UTC
    utc_dt = local_to_utc(data.date, data.time, lat, lon)

    jd = swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0,
    )

    # 2️⃣ 计算宫位（Placidus）
    houses = swe.houses(jd, lat, lon, b"P")
    asc_longitude = houses[1][0]
    armc = houses[1][2]  # ARMC
    eps = swe.calc_ut(jd, swe.ECL_NUT)[0][0]  # obliquity

    planets_result = {}
    planet_longitudes = {}

    # 3️⃣ 计算行星
    for name, planet_id in PLANETS.items():
        calc_result = swe.calc_ut(jd, planet_id)

        longitude = calc_result[0][0]
        speed = calc_result[0][3]
        planet_longitudes[name] = longitude

        longitude = calc_result[0][0]
        latitude = calc_result[0][1]  # 行星黄纬

        house_float = swe.house_pos(
            armc,
            lat,
            eps,
            (longitude, latitude),  # 注意这里必须是 tuple
            b"P",
        )

        house_number = int(house_float + 1e-6)

        planets_result[name] = {
            **longitude_to_sign(longitude),
            "house": house_number,
            "retrograde": speed < 0,
        }

    # 4️⃣ 相位
    aspects = calculate_aspects(planet_longitudes)

    # 5️⃣ features（给 RAG 用）
    features = []

    for name, pdata in planets_result.items():
        features.append(f"{name}_in_{pdata['sign'].lower()}")
        features.append(f"{name}_in_{pdata['house']}_house")

        if pdata["retrograde"]:
            features.append(f"{name}_retrograde")

    for aspect in aspects:
        p1, p2 = aspect["between"]
        features.append(f"{p1}_{aspect['type']}_{p2}")

    features.append(f"ascendant_in_{longitude_to_sign(asc_longitude)['sign'].lower()}")

    return {
        "planets": planets_result,
        "ascendant": longitude_to_sign(asc_longitude),
        "aspects": aspects,
        "features": features,
    }
