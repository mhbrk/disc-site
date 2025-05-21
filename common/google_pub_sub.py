import base64
import json
from fastapi import HTTPException

def extract_pubsub_message(payload: dict) -> dict:
    """
    Extracts the real message payload.

    - If running locally (no "message" field), assume payload is already clean.
    - If running via Google Pub/Sub push, decode "message.data" base64 field.
    """
    # If it's a Google Pub/Sub push event
    if "message" in payload and "data" in payload["message"]:
        try:
            encoded_data = payload["message"]["data"]
            decoded_bytes = base64.b64decode(encoded_data)
            decoded_json = json.loads(decoded_bytes)
            return decoded_json
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid Pub/Sub message format: {e}")

    # If it's a direct normal payload (e.g., from localhost testing)
    return payload