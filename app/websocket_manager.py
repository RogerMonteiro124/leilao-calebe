from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self.participants: set[WebSocket] = set()
        self.admins: set[WebSocket] = set()

    async def connect_participant(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.participants.add(websocket)

    async def connect_admin(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.admins.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.participants.discard(websocket)
        self.admins.discard(websocket)

    async def _broadcast(self, sockets: set[WebSocket], payload: dict) -> None:
        disconnected: list[WebSocket] = []
        for websocket in list(sockets):
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket)

    async def broadcast_participants(self, payload: dict) -> None:
        await self._broadcast(self.participants, payload)

    async def broadcast_admins(self, payload: dict) -> None:
        await self._broadcast(self.admins, payload)

    async def broadcast_all(self, payload: dict) -> None:
        await self.broadcast_participants(payload)
        await self.broadcast_admins(payload)


manager = WebSocketManager()
