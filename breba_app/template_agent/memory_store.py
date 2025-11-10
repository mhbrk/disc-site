from collections import defaultdict
from typing import Dict, List, Tuple

from breba_app.template_agent.baml_client.stream_types import LLMMessage

# Keyed by (user_name, product_id)
_messages_store: Dict[Tuple[str, str], List[LLMMessage]] = defaultdict(list)


def get_messages(user_name: str, product_id: str) -> list[LLMMessage]:
    return _messages_store[(user_name, product_id)]


def save_messages(user_name: str, product_id: str, messages: list[LLMMessage]) -> None:
    _messages_store[(user_name, product_id)] = messages
