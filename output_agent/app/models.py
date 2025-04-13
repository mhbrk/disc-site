from enum import Enum
from typing import Any, Literal, List, Union, Annotated
from uuid import uuid4

from pydantic import BaseModel, Field, TypeAdapter


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"
    UNKNOWN = "unknown"


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str
    metadata: dict[str, Any] | None = None


class Message(BaseModel):
    role: Literal["user", "agent"]
    parts: List[TextPart]
    metadata: dict[str, Any] | None = None


class PushNotificationConfig(BaseModel):
    url: str


class TaskSendParams(BaseModel):
    id: str
    sessionId: str = Field(default_factory=lambda: uuid4().hex)
    message: Message
    pushNotification: PushNotificationConfig | None = None
    historyLength: int | None = None
    metadata: dict[str, Any] | None = None


class JSONRPCMessage(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str | None = Field(default_factory=lambda: uuid4().hex)


class JSONRPCRequest(JSONRPCMessage):
    method: str
    params: dict[str, Any] | None = None


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Any | None = None


class JSONRPCResponse(JSONRPCMessage):
    result: Any | None = None
    error: JSONRPCError | None = None


class SendTaskRequest(JSONRPCMessage):
    method: Literal["tasks/send"] = "tasks/send"
    params: TaskSendParams


A2ARequest = TypeAdapter(
    Annotated[
        Union[
            SendTaskRequest,
            # Future: Add other RPC types like GetTaskRequest here
        ],
        Field(discriminator="method")
    ]
)
