import logging

from langchain_core.messages import UsageMetadata
from langchain_core.messages.ai import add_usage

from breba_app.models.product import Product

logger = logging.getLogger(__name__)

INPUT_TOKEN_COEFFICIENT = 2 / 1_000_000  # $2 per 1M tokens
OUTPUT_TOKEN_COEFFICIENT = 8 / 1_000_000  # $8 per 1M tokens


async def report_usage(username: str, product_id: str, usage_metadata: dict[str, UsageMetadata]) -> None:
    try:
        product = await Product.find_one(Product.product_id == product_id)
        aggregate_metadata = None
        for model, metadata in usage_metadata.items():
            aggregate_metadata = add_usage(aggregate_metadata, metadata)
        amount = (
                aggregate_metadata.get("input_tokens", 0) * INPUT_TOKEN_COEFFICIENT +
                usage_metadata.get("output_tokens", 0) * OUTPUT_TOKEN_COEFFICIENT
        )
        await product.increment_cost(amount)
    except Exception as e:
        # We will swallow errors because they should not impact client, this is just for analytics
        logger.error(f"Failed to update product usage for {username}, product_id: {product_id}, amount: {amount}")
        logger.error(e)
