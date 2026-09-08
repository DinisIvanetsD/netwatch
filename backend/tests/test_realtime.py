from fastapi.testclient import TestClient

from main import app


def test_websocket_sends_ready_event() -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as websocket:
        message = websocket.receive_json()

    assert message == {
        "event": "system.ready",
        "data": {"message": "NetWatch real-time channel connected"},
    }
