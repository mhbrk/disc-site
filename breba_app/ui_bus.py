import chainlit as cl

from breba_app.models.product import Product


async def send_specification_to_ui(specification: str):
    await cl.send_window_message({"method": "to_builder", "body": specification})


async def send_index_html_to_ui(html: str):
    await cl.send_window_message({"method": "to_generator", "body": html})
    await cl.send_window_message({"method": "to_generator", "body": "__completed__"})


async def send_index_html_chunk_to_ui(html: str):
    await cl.send_window_message({"method": "to_generator", "body": html})


async def update_products_list(products: list[Product]):
    products_list = [{"product_id": product.product_id, "name": product.name, "active": product.active} for product in
                     products]
    await cl.send_window_message({"method": "update_products_list", "body": products_list})


async def update_versions_list(versions: list[int], active: int):
    await cl.send_window_message({"method": "update_versions_list", "body": {"versions": versions, "active": active}})