from common.storage import upload_site
from models.deployment import Deployment
from models.product import Product
from models.user import User


async def run_deployment(username: str, product_id: str, deployment_id: str) -> str:
    # TODO: optimize this. User should be fully stored in session at login
    # TODO: optimize this. Product_id should come with the request from the forntend
    #  (in fact this is a bug that product is stored in session). The internal id should be mapped on the backend
    product = await Product.find_one(Product.product_id == product_id)
    user = await User.find_one(User.username == username)
    try:
        deployment = await Deployment.get_or_create(deployment_id, product.id, user.id)
        url = upload_site(username, product_id, str(deployment.deployment_id))
        return f"Deployed your website to: {url}"
    except Exception as e:
        return f"Could not deploy to {deployment_id}. It is probably already taken by another user"
