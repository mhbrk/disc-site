from datetime import datetime
from enum import Enum
from typing import Any, Literal, List, Union, Annotated
from uuid import uuid4

from pydantic import BaseModel, Field, TypeAdapter, field_serializer


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

class TaskStatus(BaseModel):
    state: TaskState
    message: Message | None = None
    timestamp: datetime = Field(default_factory=datetime.now)

    @field_serializer("timestamp")
    def serialize_dt(self, dt: datetime, _info):
        return dt.isoformat()

class Artifact(BaseModel):
    name: str | None = None
    description: str | None = None
    parts: List[TextPart]
    metadata: dict[str, Any] | None = None
    index: int = 0
    append: bool | None = None
    lastChunk: bool | None = None


class Task(BaseModel):
    id: str
    sessionId: str | None = None
    status: TaskStatus
    artifacts: List[Artifact] | None = None
    history: List[Message] | None = None
    metadata: dict[str, Any] | None = None

class SendTaskResponse(JSONRPCResponse):
    result: Task | None = None

A2ARequest = TypeAdapter(
    Annotated[
        Union[
            SendTaskRequest,
            # Future: Add other RPC types like GetTaskRequest here
        ],
        Field(discriminator="method")
    ]
)
