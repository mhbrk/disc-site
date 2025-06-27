import datetime
from uuid import uuid4

from beanie import Document, Link
from pydantic import Field

from .product import Product


class Deployment(Document):
    deployment_id: str = Field(default_factory=lambda: uuid4().hex)
    product: Link[Product]
    deployed_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))
    name: str

    class Settings:
        name = "deployments"
