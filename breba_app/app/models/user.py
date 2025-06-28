import datetime
from typing import List, Optional

from beanie import Document, BackLink
from pydantic import Field

from ..llm_utils import get_product_name
from ..models.product import Product


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

    @classmethod
    async def create_product_for(cls, user_name: str, product_id: str, product_spec: str):
        user_obj = await User.find_one(User.username == user_name)
        product_name = await get_product_name(product_spec)
        product = Product(product_id=product_id, user=user_obj, name=product_name)
        await product.insert()

