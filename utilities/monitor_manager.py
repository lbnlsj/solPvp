import asyncio
from datetime import datetime
from solana.rpc.websocket_api import connect
from solders.pubkey import Pubkey
from solders.rpc.config import RpcTransactionLogsFilter, RpcTransactionLogsFilterMentions
from solana.rpc.commitment import Commitment
import json
import base64
import struct
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
        self.endpoint = "wss://mainnet.helius-rpc.com/?api-key=bc8bd2ae-8330-4a02-9c98-2970d98545cd"
        self.subscription_id = None
        self.websocket = None
        self.is_running = False
        self.callbacks = []
        self.monitor_task = None
        self.ping_interval = 30  # Send ping every 30 seconds
        self.ping_timeout = 10  # Wait 10 seconds for pong response

        # Token program constants
        self.TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        self.ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
        self.PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

    async def keepalive(self):
        """Maintain WebSocket connection with periodic pings"""
        while self.is_running and self.websocket:
            try:
                await self.websocket.ping()
                try:
                    await asyncio.wait_for(self.websocket.pong(), timeout=self.ping_timeout)
                except asyncio.TimeoutError:
                    print("Ping timeout, reconnecting...")
                    await self.reconnect()
                    break
                await asyncio.sleep(self.ping_interval)
            except Exception as e:
                print(f"Keepalive error: {e}")
                await self.reconnect()
                break

    async def reconnect(self):
        """Reconnect the WebSocket connection"""
        print("Attempting to reconnect...")
        try:
            # if self.websocket:
            #     await self.websocket.close()
            self.websocket = None
            self.subscription_id = None
            self.is_running = False
            await self.start_monitoring()
        except Exception as e:
            print(f"Reconnection failed: {e}")
            self.is_running = False

    async def start_monitoring(self, program_id: Optional[str] = None):
        """Start monitoring token program logs without blocking"""
        if self.is_running:
            return

        self.is_running = True
        program_id = program_id or self.TOKEN_PROGRAM_ID

        try:
            async with connect(self.endpoint) as websocket:
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

                # Start keepalive task
                keepalive_task = asyncio.create_task(self.keepalive())

                while self.is_running:
                    try:
                        msg = await websocket.recv()
                        await self.handle_log_message(msg[0])
                    except Exception as e:
                        if isinstance(e, asyncio.CancelledError):
                            break
                        print(f"Error handling message: {e}")
                        if not self.is_running:
                            break
                        await self.reconnect()
                        break

                # Cancel keepalive task when monitoring stops
                keepalive_task.cancel()
                try:
                    await keepalive_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            print(f"Error in monitoring: {e}")
            # self.is_running = False
            # raise
            await self.reconnect()
        finally:
            self.is_running = False
            await self.stop_monitoring()

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

    def add_callback(self, callback: Callable):
        """
        Add callback function to handle token events
        Args:
            callback: Function to call when token event is detected
        """
        self.callbacks.append(callback)

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

    @staticmethod
    def parse_create_event_log(base64_log: str) -> Optional[TokenCreationInfo]:
        """
        解析创建事件日志数据，带有健壮的错误处理
        参数:
            base64_log: Base64编码的日志数据
        返回:
            成功则返回TokenCreationInfo，失败返回None
        """
        try:
            buffer = base64.b64decode(base64_log)
            offset = [8]  # 跳过鉴别器

            def parse_string() -> str:
                try:
                    length = int.from_bytes(buffer[offset[0]:offset[0] + 4], 'little')
                    offset[0] += 4

                    # 添加边界检查
                    if offset[0] + length > len(buffer):
                        raise ValueError(f"字符串长度 {length} 超出缓冲区边界")

                    # 首先尝试 UTF-8
                    try:
                        string_data = buffer[offset[0]:offset[0] + length].decode('utf-8')
                    except UnicodeDecodeError:
                        # 降级处理非UTF-8数据
                        raw_bytes = buffer[offset[0]:offset[0] + length]
                        # 过滤掉不可打印字符并解码
                        string_data = ''.join(chr(b) if 32 <= b <= 126 else '_' for b in raw_bytes)

                    offset[0] += length
                    return string_data.strip()
                except Exception as e:
                    print(f"解析字符串时在偏移量 {offset[0]} 处发生错误: {e}")
                    # 错误时返回占位符
                    return "unknown"

            def parse_public_key() -> str:
                if offset[0] + 32 > len(buffer):
                    raise ValueError("缓冲区太短，无法解析公钥")
                key_bytes = buffer[offset[0]:offset[0] + 32]
                offset[0] += 32
                return str(Pubkey(key_bytes))

            try:
                name = parse_string()
                symbol = parse_string()
                _ = parse_string()  # uri
                mint = parse_public_key()

                # 验证解析的数据
                if not all([name, symbol, mint]):
                    raise ValueError("缺少必需的字段")

                return TokenCreationInfo(
                    name=name,
                    symbol=symbol,
                    mint=mint,
                    date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            except Exception as e:
                print(f"解析代币数据时发生错误: {e}")
                print(f"缓冲区长度: {len(buffer)}, 当前偏移量: {offset[0]}")
                # 可选的调试输出
                # print("缓冲区十六进制:", buffer.hex())
                return None

        except Exception as e:
            print(f"解码base64数据时发生错误: {e}")
            return None

    def is_pump_token_creation(self, logs: List[str]) -> Optional[TokenCreationInfo]:
        """
        Check if logs indicate pump token creation
        Args:
            logs: List of transaction log strings
        Returns:
            TokenCreationInfo if pump token creation detected
        """
        program_data_logs = [d for d in logs if len(d) > 200 and 'Program data:' in d]
        if not program_data_logs:
            return None

        try:
            return self.parse_create_event_log(program_data_logs[0].split('Program data:')[1].strip())
        except Exception as e:
            print(f"Error checking pump token creation: {e}")
            return None

    async def handle_log_message(self, msg):
        """
        Handle incoming websocket log message
        Args:
            msg: WebSocket message
        """
        try:
            if hasattr(msg, 'result'):
                result = msg.result
                if hasattr(result, 'value'):
                    value = result.value
                    if hasattr(value, 'signature') and hasattr(value, 'logs'):
                        tx_signature = value.signature
                        logs = value.logs

                        token_info = self.is_pump_token_creation(logs)
                        if token_info:
                            print(f"New token detected: {token_info}")
                            print(f"Transaction: https://solscan.io/tx/{tx_signature}")

                            # Notify all callbacks
                            for callback in self.callbacks:
                                await callback(token_info, tx_signature)

            return True
        except Exception as e:
            print(f"Error processing message: {e}")
            return False

    async def stop_monitoring(self):
        """Stop monitoring logs and clean up"""
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
