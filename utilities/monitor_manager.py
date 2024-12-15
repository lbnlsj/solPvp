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
        """
        Initialize the Solana logs monitor
        Args:
            websocket_url: WebSocket endpoint URL
        """
        self.endpoint = websocket_url or "wss://mainnet.helius-rpc.com/?api-key=bc8bd2ae-8330-4a02-9c98-2970d98545cd"
        self.subscription_id = None
        self.websocket = None
        self.is_running = False
        self.callbacks = []

        # Token program constants
        self.TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        self.ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
        self.PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

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
        Parse create event log data
        Args:
            base64_log: Base64 encoded log data
        Returns:
            TokenCreationInfo if successful
        """
        try:
            buffer = base64.b64decode(base64_log)
            offset = [8]  # Skip discriminator

            def parse_string() -> str:
                length = int.from_bytes(buffer[offset[0]:offset[0] + 4], 'little')
                offset[0] += 4
                string_data = buffer[offset[0]:offset[0] + length].decode('utf-8')
                offset[0] += length
                return string_data

            def parse_public_key() -> str:
                key_bytes = buffer[offset[0]:offset[0] + 32]
                offset[0] += 32
                return str(Pubkey(key_bytes))

            name = parse_string()
            symbol = parse_string()
            _ = parse_string()  # uri
            mint = parse_public_key()

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

    async def start_monitoring(self, program_id: Optional[str] = None):
        """
        Start monitoring token program logs
        Args:
            program_id: Program ID to monitor (defaults to Token program)
        """
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

                while self.is_running:
                    msg = await websocket.recv()
                    await self.handle_log_message(msg[0])

        except Exception as e:
            print(f"Error in monitoring: {e}")
            self.is_running = False
            await self.stop_monitoring()
            raise

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