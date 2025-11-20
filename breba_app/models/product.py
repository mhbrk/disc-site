import datetime
from typing import List, Optional
from uuid import uuid4

from beanie import Document, Link, BackLink
from beanie.odm.operators.update.general import Set
from pydantic import Field

from .user import User


class Product(Document):
    product_id: str = Field(default_factory=lambda: uuid4().hex)
    name: Optional[str] = None
    user: Link[User]
    active: bool = False
    cost: float = 0
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))

    # Back-reference to deployments
    deployments: Optional[List[BackLink["Deployment"]]] = Field(
        default_factory=list,
        original_field="product"
    )

    class Settings:
        name = "products"

    async def increment_cost(self, amount: float):
        """Atomically increment the product's cost"""
        await self.inc({Product.cost: amount})


async def create_blank_product_for(product_id: str, user_name: str, product_name: str, active: bool):
    user_obj = await User.find_one(User.username == user_name)

    # Clear all active products
    await Product.find(Product.user.id == user_obj.id, Product.active == True).update(
        Set({Product.active: False})
    )

    product = Product(product_id=product_id, user=user_obj, name=product_name, active=active)
    await product.insert()
    return product


async def set_product_active(user_name: str, product_id: str):
    user_obj = await User.find_one(User.username == user_name)

    # Clear all active products
    await Product.find(Product.user.id == user_obj.id, Product.active == True).update(
        Set({Product.active: False})
    )

    product = await Product.find_one(Product.product_id == product_id)
    await product.update(Set({Product.active: True}))


async def create_or_update_product_for(user_name: str, product_id: str | None = None,
                                       product_name: str | None = None):
    user_obj = await User.find_one(User.username == user_name, fetch_links=False)

    # Clear all active products
    await Product.find(Product.user.id == user_obj.id, Product.active == True).update(
        Set({Product.active: False})
    )

    # Insert new active product
    product = Product(product_id=product_id, user=user_obj, name=product_name, active=True)
    await Product.find_one(Product.product_id == product_id).upsert(
        Set({
            Product.name: product_name,
            Product.active: True
        }),
        on_insert=product
    )
    return product

async def delete_product_and_deployments(user_name: str, product_id: str) -> bool:
    """
    Delete a product (by product_id and user_name) and all its deployments atomically.
    Returns True if a product was deleted, False if not found.
    """

    # Find the user first
    user_obj = await User.find_one(User.username == user_name, fetch_links=False)
    if not user_obj:
        return False

    # Use the underlying Motor client to start a transaction
    client: AsyncIOMotorClient = Product.get_motor_collection().database.client  # type: ignore

    async with await client.start_session() as session:
        async with session.start_transaction():
            # Find the product belonging to this user
            product: Optional[Product] = await Product.find_one(
                Product.product_id == product_id,
                Product.user.id == user_obj.id,
                session=session,
            )

            if not product:
                # Nothing to delete; transaction will auto-rollback
                return False

            # Delete all deployments linked to this product
            await Deployment.find(
                Deployment.product.id == product.id,  # link field
                session=session,
            ).delete_many()

            # Delete the product itself
            await product.delete(session=session)

            return True
