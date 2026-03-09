from typing import Optional

from pydantic import BaseModel


class ChartRequest(BaseModel):
    date: str  # YYYY-MM-DD
    time: str  # HH:MM (local time)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ChatRequest(BaseModel):
    date: str  # YYYY-MM-DD
    time: str  # HH:MM (local time)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    question: str


class SimpleChatRequest(BaseModel):
    wechat_id: str
    message: str


class UserRegisterRequest(BaseModel):
    wechat_id: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_name: Optional[str] = None


class PlanetPosition(BaseModel):
    sign: str
    degree: float


class ChartResponse(BaseModel):
    sun: PlanetPosition
    moon: PlanetPosition
    ascendant: PlanetPosition


class PromptUpdateRequest(BaseModel):
    content: str
