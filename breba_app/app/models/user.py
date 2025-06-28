import datetime
from typing import List, Optional

from beanie import Document, BackLink
from pydantic import Field


class User(Document):
    username: str = Field(..., unique=True)
    password_hash: str
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))

    # Back-reference: products created by this user
    products: Optional[List[BackLink["Product"]]] = Field(
        default_factory=list,
        original_field="user"
    )

    class Settings:
        name = "users"

