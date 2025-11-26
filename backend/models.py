from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    token: str
    user: dict

class SummarizeRequest(BaseModel):
    url: str
    chat_id: Optional[str] = None
    messages: Optional[List[dict]] = None

class SummarizeResponse(BaseModel):
    summary: str
    title: str
    chat_id: str

class RenameRequest(BaseModel):
    title: str

class HistoryResponse(BaseModel):
    chats: List[dict]

class Message(BaseModel):
    id: str
    type: str
    content: str
    url: Optional[str] = None
    timestamp: datetime

class Chat(BaseModel):
    id: str
    title: str
    messages: List[Message]
    timestamp: datetime
