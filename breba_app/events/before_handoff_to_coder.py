from pydantic import BaseModel, ConfigDict

from breba_app.coder_agent.baml_client.stream_types import LLMMessage


class BeforeHandoffToCoder(BaseModel):
    """
    Event payload for "BeforeHandoffToCoder".
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_name: str
    product_id: str
    messages: list[LLMMessage]
    executive_summary: str
