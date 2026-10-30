"""In-memory registry of WebSocket connections used to push notifications."""

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Keeps track of open WebSocket connections, grouped by user id.

    The registry lives in the memory of one process, so it only works with
    a single worker. One user can have several connections (browser tabs).
    """

    def __init__(self) -> None:
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        """
        Accept a WebSocket connection and register it for the user.

        A user can have several open connections at once (for example, two
        browser tabs), so every connection is added to the user's list.

        Args:
            user_id (int): Id of the authenticated user.
            websocket (WebSocket): The connection to accept and store.
        """
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        """
        Remove a connection from the user's list.

        Safe to call more than once for the same connection: if the user or
        the connection is unknown, nothing happens. When the user has no
        connections left, the user is removed from the registry.

        Args:
            user_id (int): Id of the user the connection belongs to.
            websocket (WebSocket): The connection to remove.
        """
        connections = self.active_connections.get(user_id)
        if not connections or websocket not in connections:
            return

        connections.remove(websocket)
        if not connections:
            del self.active_connections[user_id]

    async def send_to_user(self, user_id: int, data: dict) -> None:
        """
        Send a JSON message to all open connections of the user.

        Does nothing if the user is offline. A connection that fails to
        receive the message is logged and removed, and the error is not
        raised, so a closed browser tab never breaks the request that
        triggered the notification.

        Args:
            user_id (int): Id of the user who should receive the message.
            data (dict): JSON-serializable message.
        """
        for websocket in list(self.active_connections.get(user_id, [])):
            try:
                await websocket.send_json(data)
            except Exception:
                logger.warning(
                    "Could not send a message to user %s, dropping the "
                    "connection",
                    user_id,
                )
                self.disconnect(user_id, websocket)


manager = ConnectionManager()
