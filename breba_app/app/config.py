import os

from beanie import init_beanie
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from breba_app.app.models.deployment import Deployment
from breba_app.app.models.product import Product
from models.user import User

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")


async def init_db():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_database('breba')

    User.model_rebuild(_types_namespace={"Product": Product})
    Product.model_rebuild(_types_namespace={"User": User, "Deployment": Deployment})
    Deployment.model_rebuild(_types_namespace={"Product": Product})

    await init_beanie(database=db, document_models=[User, Product, Deployment])
