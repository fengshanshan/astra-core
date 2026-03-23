from typing import Optional

from pydantic import BaseModel


class ChartRequest(BaseModel):
    date: str  # YYYY-MM-DD
    time: str  # HH:MM (local time)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SimpleChatRequest(BaseModel):
    wechat_id: str
    message: str
    conversation_id: Optional[str] = None


class SimpleChatResponse(BaseModel):
    answer: str
    conversation_id: str
    stage: int
    suggest_new_conversation: bool


class UserRegisterRequest(BaseModel):
    wechat_id: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_name: Optional[str] = None


class PromptUpdateRequest(BaseModel):
    content: str


class ConversationCreateRequest(BaseModel):
    wechat_id: str


class ConversationOut(BaseModel):
    id: str
    summary: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
