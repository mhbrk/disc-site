import os
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from models.user import User
from dotenv import load_dotenv

load_dotenv()  # load variables from a .env file if present

MONGO_URI = os.getenv("MONGO_URI")

async def init_db():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_database('breba')
    await init_beanie(database=db, document_models=[User])
