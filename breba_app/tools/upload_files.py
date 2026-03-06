import asyncio
from pathlib import Path

from PIL import Image

from breba_app.storage import save_image_file_to_private

MAX_CONCURRENT_UPLOADS = 10
sem = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)

def get_image_dimensions(path: Path):
    with Image.open(path) as img:
        return img.width, img.height

async def process_file(user_name: str, product_id: str, file_path: Path, file_name: str, description: str):
    async with sem:
        # get dimensions in a thread (Pillow is blocking)
        width, height = await asyncio.to_thread(get_image_dimensions, file_path)
        description = f"{description}. Image dimensions: {width}x{height}"

        blob_path = await asyncio.to_thread(
            save_image_file_to_private,
            user_name,
            product_id,
            file_name,
            file_path.as_posix(),
            description
        )

        return blob_path