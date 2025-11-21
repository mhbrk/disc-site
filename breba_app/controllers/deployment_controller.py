import logging

from breba_app.models.deployment import Deployment
from breba_app.models.product import Product
from breba_app.models.user import User
from breba_app.storage import upload_site

logger = logging.getLogger(__name__)


async def run_deployment(username: str, product: Product, deployment_id: str) -> str:
    # TODO: optimize this. User should be fully stored in session at login
    # TODO: optimize this. Product_id should come with the request from the forntend
    #  (in fact this is a bug that product is stored in session). The internal id should be mapped on the backend
    user = await User.find_one(User.username == username)
    try:
        deployment = await Deployment.get_or_create(deployment_id, product.id, user.id)
        url = await upload_site(username, product.product_id, deployment.deployment_id)
        logger.info(f"User: {username}, Product: {product.product_id}, uploaded site to url: {url}")

        await deployment.update_deployment_timestamp()
        return f"Deployed your website to: {url}"
    except Exception as e:
        logger.error(f"Could not deploy to {deployment_id}. Error: {e}")
        return f"Could not deploy to {deployment_id}. It is probably already taken by another user"
