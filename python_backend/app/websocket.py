# from typing import List, Dict
# from fastapi import WebSocket

# class ConnectionManager:
#     def __init__(self):
#         self.active_connections: List[WebSocket] = []

#     async def connect(self, websocket: WebSocket):
#         await websocket.accept()
#         self.active_connections.append(websocket)
#         print(f"WebSocket connected: {websocket.client}")

#     def disconnect(self, websocket: WebSocket):
#         self.active_connections.remove(websocket)
#         print(f"WebSocket disconnected: {websocket.client}")

#     async def send_personal_message(self, message: str, websocket: WebSocket):
#         await websocket.send_text(message)

#     async def broadcast_json(self, data: Dict):
#         # print(f"Broadcasting: {data['type']}") # Debugging
#         for connection in self.active_connections:
#             try:
#                 await connection.send_json(data)
#             except RuntimeError as e:
#                 print(f"Error sending to WebSocket {connection.client}: {e}. Disconnecting dead client.")
#                 self.disconnect(connection)


# manager = ConnectionManager()




from typing import List, Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"WebSocket connected: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"WebSocket disconnected: {websocket.client}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast_json(self, data: Dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except RuntimeError as e:
                print(f"Error sending to WebSocket {connection.client}: {e}. Disconnecting dead client.")
                self.disconnect(connection)

manager = ConnectionManager()