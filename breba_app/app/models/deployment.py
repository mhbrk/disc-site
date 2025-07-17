import datetime
import logging

from beanie import Document, Link
from bson import DBRef
from pydantic import Field
from pymongo import IndexModel

from .product import Product
from .user import User

logger = logging.getLogger(__name__)


class Deployment(Document):
    deployment_id: str
    user: Link[User]
    product: Link[Product]
    deployed_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))

    class Settings:
        name = "deployments"
        indexes = [
            IndexModel([("deployment_id", 1)], unique=True),
            IndexModel([("user", 1)]),
            IndexModel([("user", 1), ("deployment_id", 1)]),
            IndexModel([("product", 1)])
        ]

    @classmethod
    async def get_or_create(cls, deployment_id: str, product_id: str, username: str) -> tuple["Deployment", bool]:
        """
        Get existing deployment or create new one atomically using Beanie's upsert.
        Returns (deployment, created) where created is True if new deployment was created.

        Raises ValueError if:
        - Deployment exists but belongs to different user
        - Product doesn't exist or doesn't belong to user
        - User does not exist
        """
        # Find the user
        user = await User.find_one(User.username == username)

        if not user:
            raise ValueError(f"User {username} does not exist")

        # Verify product exists and belongs to the user
        product = await Product.find_one(
            Product.product_id == product_id,
            Product.user.id == user.id,
        )

        if not product:
            raise ValueError(f"Product {product_id} does not belong to user {username}")

        # Create the document that would be inserted if not found
        result = await Deployment.get_motor_collection().update_one(
            {"deployment_id": deployment_id},
            {
                "$setOnInsert": {
                    "deployment_id": deployment_id,
                    "user": user.id,
                    "product": DBRef("products", product.id),
                    "deployed_at": datetime.datetime.now(datetime.UTC)
                }
            },
            upsert=True
        )

        deployment: None | cls = None
        new_document = result.upserted_id is not None
        # Check if it was inserted or already existed
        if new_document:
            deployment = await Deployment.get(result.upserted_id)
        else:
            deployment = await Deployment.find_one(Deployment.deployment_id == deployment_id)

        if deployment is None:
            raise RuntimeError("Upsert operation failed unexpectedly")

        # Check ownership
        if deployment is not None and deployment.user.ref.id != user.id:
            raise ValueError(f"Deployment {deployment_id} exists but belongs to a different user")

        return deployment, new_document
