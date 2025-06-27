import datetime
from typing import List, Optional
from uuid import uuid4

from beanie import Document, Link, BackLink
from pydantic import Field

from .user import User


class Product(Document):
    product_id: str = Field(default_factory=lambda: uuid4().hex)
    name: Optional[str] = None
    user: Link[User]
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))

    # Back-reference to deployments
    deployments: Optional[List[BackLink["Deployment"]]] = Field(
        default_factory=list,
        original_field="product"
    )

    class Settings:
        name = "products"
