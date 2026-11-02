"""Send one obs-websocket v5 request and print the response JSON.

    python obs.py GetRecordStatus
    python obs.py SetCurrentProgramScene '{"sceneName": "Demo Recorder"}'

Uses OBS_WEBSOCKET_URL (default ws://127.0.0.1:4455) and OBS_WEBSOCKET_PASSWORD when
authentication is enabled in OBS > Tools > WebSocket Server Settings.
"""
import base64
import hashlib
import json
import os
import sys
import uuid

import websocket


def _auth(password, challenge, salt):
    secret = base64.b64encode(hashlib.sha256((password + salt).encode()).digest()).decode()
    return base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()


def request(request_type, data=None):
    url = os.environ.get("OBS_WEBSOCKET_URL", "ws://127.0.0.1:4455")
    try:
        ws = websocket.create_connection(url, timeout=30)
    except (ConnectionRefusedError, OSError) as error:
        raise SystemExit(f"Cannot reach OBS at {url}. Start OBS and enable Tools > WebSocket Server Settings. ({error})")
    try:
        hello = json.loads(ws.recv())["d"]
        identify = {"rpcVersion": 1, "eventSubscriptions": 0}
        if hello.get("authentication"):
            password = os.environ.get("OBS_WEBSOCKET_PASSWORD")
            if not password:
                raise RuntimeError("OBS requires a password; set OBS_WEBSOCKET_PASSWORD.")
            a = hello["authentication"]
            identify["authentication"] = _auth(password, a["challenge"], a["salt"])
        ws.send(json.dumps({"op": 1, "d": identify}))
        if json.loads(ws.recv())["op"] != 2:
            raise RuntimeError("OBS did not accept the connection")
        request_id = str(uuid.uuid4())
        ws.send(json.dumps({"op": 6, "d": {"requestType": request_type, "requestId": request_id, "requestData": data or {}}}))
        while True:
            message = json.loads(ws.recv())
            if message["op"] == 7 and message["d"]["requestId"] == request_id:
                status = message["d"]["requestStatus"]
                if not status["result"]:
                    raise RuntimeError(f"{request_type} failed: {json.dumps(status)}")
                return message["d"].get("responseData", {})
    finally:
        ws.close()


if __name__ == "__main__":
    payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
    print(json.dumps(request(sys.argv[1], payload), ensure_ascii=True))
