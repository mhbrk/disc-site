from pydantic import BaseModel, ConfigDict

from breba_app.filesystem import InMemoryFileStore


class CoderCompleted(BaseModel):
    """
    Event payload for "CodeCompleted".
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_name: str
    product_id: str
    file_store: InMemoryFileStore