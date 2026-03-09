ZODIAC_SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]


def longitude_to_sign(longitude: float):
    index = int(longitude // 30)
    sign = ZODIAC_SIGNS[index]
    degree = round(longitude % 30, 2)

    return {"sign": sign, "degree": degree}
