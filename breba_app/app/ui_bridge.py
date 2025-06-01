import asyncio
import logging

from starlette.websockets import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


# TODO: This function is suppoed to keep connection alive, maybe there is a better way
async def handle_socket_connection(
        websocket: WebSocket,
        metadata: dict,
):
    """
    Helps manage socket connections for each session connected to this server
    :param websocket: new websocket connection
    :param metadata: metadata about the websocket for logging
    """
    await websocket.accept()

    logger.info(f"Connected socket for session: {metadata}")

    try:
        while True:
            await asyncio.sleep(1)
            # TODO: enable keep alive mechanism
            # await websocket.send_text("__ping__")
            # pong = await asyncio.wait_for(websocket.receive_text(), timeout=ping_interval)
            # if pong != "__pong__":
            #     raise WebSocketDisconnect(1006, f"Pong not received: {pong}")
    except asyncio.TimeoutError:
        logger.info(f"Disconnected socket [{metadata}], due to timeout")
    except WebSocketDisconnect:
        logger.info(f"Disconnected socket [{metadata}]")
    finally:
        await websocket.close()


class UIBridge:
    def __init__(
            self,
            session_id: str,
            generator_socket: WebSocket | None = None,
            user_socket: WebSocket | None = None,
            builder_socket: WebSocket | None = None,
            status_socket: WebSocket | None = None,
    ):
        self.session_id = session_id
        self.generator_socket = generator_socket
        self.user_socket = user_socket
        self.builder_socket = builder_socket
        self.status_socket = status_socket

    async def add_generator_socket(self, socket: WebSocket):
        logger.info(f"Connected generator socket for session: {self.session_id}")
        self.generator_socket = socket
        await handle_socket_connection(socket, {"name": "generator", "session": self.session_id})

    async def add_user_socket(self, socket: WebSocket):
        logger.info(f"Connected user socket for session: {self.session_id}")
        self.user_socket = socket
        await handle_socket_connection(socket, {"name": "user", "session": self.session_id})

    async def add_builder_socket(self, socket: WebSocket):
        logger.info(f"Connected builder socket for session: {self.session_id}")
        self.builder_socket = socket
        await handle_socket_connection(socket, {"name": "builder", "session": self.session_id})

    async def add_status_socket(self, socket: WebSocket):
        logger.info(f"Connected status socket for session: {self.session_id}")
        self.status_socket = socket
        await handle_socket_connection(socket, {"name": "status", "session": self.session_id})
