from datetime import datetime, timezone
from typing import Optional
from beanie import Document
from pydantic import EmailStr
from pymongo import IndexModel, ASCENDING


class User(Document):
    name: str
    email: EmailStr
    password_hash: str
    timezone: str = "Asia/Kolkata"
    created_at: datetime = None
    updated_at: datetime = None

    def model_post_init(self, __context) -> None:
        now = datetime.now(timezone.utc)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now

    class Settings:
        name = "users"
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True),
        ]
