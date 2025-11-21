from datetime import datetime, UTC

from passlib.context import CryptContext

from breba_app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def create_user(username, password):
    hashed_password = get_password_hash(password)
    user = User(username=username, password_hash=hashed_password, created_at=datetime.now(UTC))
    await user.insert()


async def change_password(username: str, current_password: str, new_password: str) -> bool:
    """Return True if password updated, False if current password invalid."""
    user = await User.find_one(User.username == username)
    if not user:
        return False
    if not verify_password(current_password, user.password_hash):
        return False
    user.password_hash = get_password_hash(new_password)
    await user.save()
    return True
