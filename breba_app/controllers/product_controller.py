from motor.motor_asyncio import AsyncIOMotorClient

from breba_app.models.deployment import Deployment
from breba_app.models.product import Product
from breba_app.models.user import User
from breba_app.storage import delete_product_files


async def delete_product_and_deployments(user_name: str, product_id: str):
    user_obj = await User.find_one(User.username == user_name, fetch_links=False)
    if not user_obj:
        raise ValueError(f"User not found: {user_name}")

    client: AsyncIOMotorClient = Product.get_motor_collection().database.client  # type: ignore

    async with await client.start_session() as session:
        async with session.start_transaction():
            product: Product | None = await Product.find_one(
                Product.product_id == product_id,
                Product.user.id == user_obj.id,
                session=session,
            )

            if not product:
                raise ValueError(f"Product not found: {product_id}")

            await Deployment.find(
                Deployment.product.id == product.id,
                session=session,
            ).delete_many()

            await product.delete(session=session)

            return True

async def delete_product(user_name: str, product_id: str):
    # Frist delete the mongodb data
   await delete_product_and_deployments(user_name, product_id)

   # If mongoDB is cleared, delete the s3 data
   await delete_product_files(user_name, product_id)
