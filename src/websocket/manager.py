import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        connections = self.active.get(user_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self.active.pop(user_id, None)

    async def disconnect_user(self, user_id: str, code: int = 4003) -> None:
        connections = list(self.active.pop(user_id, ()))
        for websocket in connections:
            try:
                await websocket.close(code=code)
            except Exception:  # noqa: BLE001 - the connection is already removed locally
                logger.info("WebSocket for disabled user %s was already closed", user_id)

    async def broadcast_to_users(self, user_ids: list[str], payload: dict) -> None:
        for user_id in user_ids:
            for websocket in list(self.active.get(user_id, ())):
                try:
                    await websocket.send_json(payload)
                except Exception:  # noqa: BLE001 - isolate and remove one stale client
                    logger.info("Removing stale WebSocket connection for user %s", user_id)
                    self.disconnect(user_id, websocket)


manager = ConnectionManager()
