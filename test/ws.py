import asyncio
import websockets


# 定义一个异步接收消息的协程
async def receive_messages(websocket: websockets.WebSocketClientProtocol):
    while True:
        try:
            message = await websocket.recv()
            print(f"Received message: {message}")
        except websockets.exceptions.ConnectionClosedOK:
            print("Connection was gracefully closed.")
            break
        except websockets.exceptions.ConnectionClosedError:
            print("Connection was closed unexpectedly.")
            break


# 定义一个异步发送消息的协程
async def send_messages(websocket: websockets.WebSocketClientProtocol):
    while True:
        message = input("Enter a message to send (or type 'exit' to close): ")
        if message == "exit":
            await websocket.close()
            break
        await websocket.send(message)
        print(f"Sent message: {message}")


# 主异步函数，用于异步启动连接、接收和发送消息
async def main():
    uri = "wss://echo.websocket.org"
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {uri}")
        receive_task = asyncio.create_task(receive_messages(websocket))
        send_task = asyncio.create_task(send_messages(websocket))
        # 等待任一子协程结束（当用户输入'stop'或链接意外关闭时）
        try:
            await asyncio.gather(receive_task, send_task)
        finally:
            print("Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
