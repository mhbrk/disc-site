import datetime
import logging

from beanie import Document, Link, PydanticObjectId
from bson import DBRef
from pydantic import Field
from pymongo import IndexModel, ReturnDocument

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
    async def get_or_create(cls, deployment_id: str, product_id: PydanticObjectId,
                            user_id: PydanticObjectId) -> "Deployment":
        """
        Get existing deployment or create new one atomically using Beanie's upsert.
        Returns (deployment, created) where created is True if new deployment was created.

        Raises ValueError if:
        - Deployment exists but belongs to different user
        - Product doesn't exist or doesn't belong to user
        - User does not exist
        """
        # The key here is that we want to insert, only if it doesn't exist, but we don't want to update it if it exists.
        # If it exists, we just want to return it after checking ownership
        result = await Deployment.get_motor_collection().find_one_and_update(
            {"deployment_id": deployment_id},
            {
                "$setOnInsert": {
                    "deployment_id": deployment_id,
                    "user": user_id,
                    "product": DBRef("products", product_id),
                    "deployed_at": datetime.datetime.now(datetime.UTC)
                }
            },
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        if result is None:
            raise RuntimeError("Upsert operation failed unexpectedly")

        deployment = Deployment.model_validate(result, from_attributes=False)

        # Check if this user owns it
        if deployment.user.ref.id != user_id:
            raise ValueError(f"Deployment {deployment_id} exists but belongs to a different user")

        return deployment
