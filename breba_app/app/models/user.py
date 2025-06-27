import datetime

from beanie import Document
from pydantic import Field


class User(Document):
    username: str = Field(..., unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))

    class Settings:
        name = "users"  # Collection name in MongoDB
