from datetime import datetime, UTC

from passlib.context import CryptContext

from models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def create_user(username, password):
    hashed_password = get_password_hash(password)

    user = User(username=username, password_hash=hashed_password, created_at=datetime.now(UTC))

    await user.insert()


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    from config import init_db

    load_dotenv()

    async def run():
        await init_db()
        await create_user("username", "pwd")


    asyncio.run(run())
