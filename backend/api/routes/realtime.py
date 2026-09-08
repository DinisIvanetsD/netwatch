from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.realtime.manager import connection_manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await connection_manager.connect(websocket)
    await websocket.send_json(
        {
            "event": "system.ready",
            "data": {"message": "NetWatch real-time channel connected"},
        }
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
