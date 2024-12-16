import asyncio
from datetime import datetime
from solana.rpc.websocket_api import connect
from solders.pubkey import Pubkey
from solders.rpc.config import RpcTransactionLogsFilter, RpcTransactionLogsFilterMentions
from solana.rpc.commitment import Commitment
import json
import base64
import time
import threading
import struct
import traceback
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass


@dataclass
class TokenCreationInfo:
    name: str
    symbol: str
    mint: str
    date: str


class MonitorManager:
    def __init__(self, websocket_url: str = None):
        self.endpoint = websocket_url or "wss://mainnet.helius-rpc.com/?api-key=bc8bd2ae-8330-4a02-9c98-2970d98545cd"
        self.subscription_id = None
        self.websocket = None
        self.is_running = False
        self.callbacks = []
        self.monitor_task = None
        self.ping_interval = 15
        self.ping_timeout = 5
        self.max_retries = 5
        self.retry_delay = 5
        self.current_retries = 0

        # Token program constants
        self.TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        self.ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
        self.PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

    async def keepalive(self):
        while 1:
            try:
                print('ping')
                if self.websocket.closed:
                    print("WebSocket closed, initiating reconnection...")
                    await self.reconnect()
                    continue

                await self.websocket.ping()
                print('ping finish')
                # try:
                #     await asyncio.wait_for(self.websocket.pong(), timeout=self.ping_timeout)
                # except asyncio.TimeoutError:
                #     print("Ping timeout, reconnecting...")
                #     await self.reconnect()
                #     continue

                await asyncio.sleep(self.ping_interval)

            except Exception as e:
                print(f"Keepalive error: {e}")
                await self.reconnect()
                await asyncio.sleep(1)

    async def reconnect(self):
        # if self.current_retries >= self.max_retries:
        #     print("Max reconnection attempts reached")
        #     self.is_running = False
        #     return

        self.current_retries += 1
        print(f"Attempting to reconnect... (attempt {self.current_retries})")

        try:
            # if self.websocket and not self.websocket.closed:
            #     await self.websocket.close()

            self.websocket = None
            self.subscription_id = None

            await asyncio.sleep(self.retry_delay)
            self.is_running = False
            await self.start_monitoring()
            self.current_retries = 0

        except Exception as e:
            print(f"Reconnection failed: {e}")
            if self.current_retries < self.max_retries:
                await self.reconnect()
            else:
                self.is_running = False

    def test(self):
        while 1:
            print('1')
            time.sleep(1)

    # 在 MonitorManager 类中修改 start_monitoring 方法
    async def start_monitoring(self, program_id: Optional[str] = None):
        if self.is_running:
            print('已在运行中')
            return

        threading.Thread(target=self.test, args=()).start()

        print('开始运行监控')
        self.is_running = True
        program_id = program_id or self.TOKEN_PROGRAM_ID

        while self.is_running:
            print('开始创建监控')
            try:
                async with connect(self.endpoint) as websocket:
                    print('监控创建成功')
                    self.websocket = websocket

                    filter_ = RpcTransactionLogsFilterMentions(
                        Pubkey.from_string(program_id)
                    )

                    await websocket.logs_subscribe(
                        filter_=filter_,
                        commitment=Commitment("processed")
                    )

                    first_resp = await websocket.recv()
                    self.subscription_id = first_resp[0].result

                    print(f"Started monitoring program: {program_id}")
                    print(f"Subscription ID: {self.subscription_id}")

                    # 使用异步迭代器模式
                    async for msg in websocket:
                        if not self.is_running:
                            break
                        try:
                            await self.handle_log_message(msg[0])
                        except Exception as e:
                            print(f"Error handling message: {e}")
                            continue

            except Exception as e:
                print(f"Connection error: {e}")
                if self.is_running:
                    print("Attempting to reconnect in 5 seconds...")
                    await asyncio.sleep(5)
                continue

            finally:
                continue

    @staticmethod
    def parse_create_event_log(base64_log: str) -> Optional[TokenCreationInfo]:
        try:
            buffer = base64.b64decode(base64_log)
            if len(buffer) < 8:
                return None

            offset = [8]  # Skip discriminator

            def parse_string() -> str:
                try:
                    if offset[0] + 4 > len(buffer):
                        return ""

                    length = int.from_bytes(buffer[offset[0]:offset[0] + 4], 'little')
                    if not (0 <= length <= 10000):  # 合理的字符串长度限制
                        return ""

                    offset[0] += 4
                    if offset[0] + length > len(buffer):
                        return ""

                    string_data = buffer[offset[0]:offset[0] + length].decode('utf-8')
                    offset[0] += length
                    return string_data
                except:
                    return ""

            def parse_public_key() -> Optional[str]:
                try:
                    if offset[0] + 32 > len(buffer):
                        return None

                    key_bytes = buffer[offset[0]:offset[0] + 32]
                    offset[0] += 32
                    return str(Pubkey(key_bytes))
                except:
                    return None

            name = parse_string()
            symbol = parse_string()
            _ = parse_string()  # uri
            mint = parse_public_key()

            if not all([name, symbol, mint]):
                return None

            return TokenCreationInfo(
                name=name,
                symbol=symbol,
                mint=mint,
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

        except Exception as e:
            print(f"Error parsing create event log: {e}")
            return None

    def is_pump_token_creation(self, logs: List[str]) -> Optional[TokenCreationInfo]:
        try:
            program_data_logs = [d for d in logs if len(d) > 200 and 'Program data:' in d]
            if not program_data_logs:
                return None

            return self.parse_create_event_log(program_data_logs[0].split('Program data:')[1].strip())
        except Exception as e:
            print(f"Error checking pump token creation: {e}")
            return None

    async def handle_log_message(self, msg):
        try:
            if not hasattr(msg, 'result'):
                return False

            result = msg.result
            if not hasattr(result, 'value'):
                return False

            value = result.value
            if not (hasattr(value, 'signature') and hasattr(value, 'logs')):
                return False

            tx_signature = value.signature
            logs = value.logs

            token_info = self.is_pump_token_creation(logs)
            if token_info:
                print(f"New token detected: {token_info}")
                print(f"Transaction: https://solscan.io/tx/{tx_signature}")

                for callback in self.callbacks:
                    try:
                        await callback(token_info, tx_signature)
                    except Exception as e:
                        print(f"Callback error: {e}")
                        continue

            return True

        except Exception as e:
            print(f"Error processing message: {e}")
            return False

    def add_callback(self, callback: Callable):
        self.callbacks.append(callback)

    async def stop_monitoring(self):
        self.is_running = False
        if self.websocket and self.subscription_id:
            try:
                await self.websocket.logs_unsubscribe(self.subscription_id)
                print(f"Stopped monitoring logs for subscription: {self.subscription_id}")
            except Exception as e:
                print(f"Error stopping monitor: {e}")
            finally:
                self.subscription_id = None
                self.websocket = None

    async def get_websocket(self):
        """Get websocket connection"""
        if self.websocket is None:
            self.websocket = await connect(self.endpoint)
        return self.websocket

    def create_filter(self, program_id: str):
        """Create program filter"""
        return RpcTransactionLogsFilterMentions(
            Pubkey.from_string(program_id)
        )

    def get_commitment(self):
        """Get commitment level"""
        return Commitment("processed")

    @staticmethod
    def parse_token_info(logs: List[str]) -> Optional[Dict]:
        """
        Parse token information from transaction logs
        Args:
            logs: List of transaction log strings
        Returns:
            Token information dictionary if successful
        """
        token_info = {
            'name': None,
            'symbol': None,
            'mint_address': None
        }

        for i, log in enumerate(logs):
            if log.startswith('Program data:'):
                try:
                    data = log.split('Program data: ')[1]
                    decoded = base64.b64decode(data)
                    readable = ''.join(chr(c) if 32 <= c <= 126 else ' ' for c in decoded)
                    parts = readable.split()
                    for j, part in enumerate(parts):
                        if j + 1 < len(parts):
                            if len(part) >= 3:
                                if token_info['name'] is None:
                                    token_info['name'] = part
                                elif token_info['symbol'] is None:
                                    token_info['symbol'] = part
                except:
                    continue

            elif "Create" in log and i > 0:
                prev_log = logs[i - 1]
                if "Invoking Token Program" in prev_log:
                    words = log.split()
                    for word in words:
                        if len(word) >= 32:
                            token_info['mint_address'] = word
                            break

        return token_info if all(token_info.values()) else None


if __name__ == '__main__':
    import signal
    import sys

    m = MonitorManager()


    # 添加测试回调函数
    async def test_callback(token_info, tx_signature):
        print("\n=== Token Creation Event ===")
        print(f"Name: {token_info.name}")
        print(f"Symbol: {token_info.symbol}")
        print(f"Mint: {token_info.mint}")
        print(f"Date: {token_info.date}")
        print(f"Transaction: {tx_signature}")
        print("=========================\n")


    m.add_callback(test_callback)


    # 处理退出信号
    def signal_handler(sig, frame):
        print('\nReceived stop signal. Shutting down...')
        m.is_running = False


    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


    async def main():
        try:
            print("Starting monitor... Press Ctrl+C to stop")
            print("Monitoring for token creation events...")

            # 监控 Pump.fun 程序
            program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
            await m.start_monitoring(program_id)

        except Exception as e:
            print(f"Error in main: {e}")
        finally:
            await m.stop_monitoring()
            print("Monitor stopped")


    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        sys.exit(0)
