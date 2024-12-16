# utilities/sniper_manager.py
from .monitor_manager import MonitorManager, TokenCreationInfo
from .wallet_manager import WalletManager
from datetime import datetime
import asyncio
from typing import Optional, Dict, Tuple
import json
import os
from .pump import buy_token, sell_token
import multiprocessing
from multiprocessing import Process, Event
import signal
from solders.keypair import Keypair


class SniperManager:
    def __init__(self, data_dir: str, monitor_manager: MonitorManager, wallet_manager: WalletManager):
        self.data_dir = data_dir
        self.monitor_manager = monitor_manager
        self.wallet_manager = wallet_manager
        self.config_file = os.path.join(data_dir, "config.json")
        self.contracts_file = os.path.join(data_dir, "contracts.json")
        self.transactions_file = os.path.join(data_dir, "transactions.json")
        self.status_file = os.path.join(data_dir, "sniper_status.json")
        self.stop_event = Event()
        self.process = None
        self.sniper_is_running = False

        # Initialize status file if it doesn't exist
        if not os.path.exists(self.status_file):
            self.save_status(False)

    def save_status(self, is_running: bool):

        self.sniper_is_running = is_running
        # with open(self.status_file, 'w') as f:
        #     json.dump({"is_running": is_running}, f)

    def get_status(self) -> bool:

        return self.sniper_is_running
        # try:
        #     with open(self.status_file, 'r') as f:
        #         status = json.load(f)
        #         return status.get("is_running", False)
        # except:
        #     return False

    @staticmethod
    def sniper_process(stop_event: Event, data_dir: str, monitor_manager: MonitorManager,
                       wallet_manager: WalletManager):
        """
        Main function that runs in the separate process
        """
        try:
            # Set up signal handlers
            def handle_signal(signum, frame):
                stop_event.set()

            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)

            # Create new event loop for this process
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def run_monitor():
                try:
                    # Add callback for token creation events
                    monitor_manager.add_callback(handle_token_creation)

                    # Start monitoring
                    program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
                    await monitor_manager.start_monitoring(program_id)
                except Exception as e:
                    print(f"Error in monitoring process: {e}")
                    stop_event.set()

            async def handle_token_creation(token_info: TokenCreationInfo, creation_tx: str):
                try:
                    # Load configuration
                    with open(os.path.join(data_dir, "config.json"), 'r') as f:
                        config = json.load(f)

                    with open(os.path.join(data_dir, "contracts.json"), 'r') as f:
                        contracts = json.load(f)

                    # Check if we should monitor this token
                    if contracts and token_info.mint not in contracts:
                        return

                    # Get available wallets
                    wallets = wallet_manager.get_all_pubkeys()
                    if not wallets:
                        print("No wallets available")
                        return

                    print(f"New token detected: {token_info.name} ({token_info.symbol})")
                    print(f"Token mint address: {token_info.mint}")
                    print(f"Creation transaction: https://solscan.io/tx/{creation_tx}")

                    if config['mode'] == 'single':
                        # 获取第一个钱包的 keypair
                        keypair = wallet_manager.get_keypair(wallets[0])
                        if not keypair:
                            print("Could not get keypair for wallet")
                            return

                        success, buy_tx = buy_token(token_info.mint, keypair, config['maxSolPerTrade'], 5)
                        if success and buy_tx:
                            print(f"Buy transaction: https://solscan.io/tx/{buy_tx}")
                            save_transaction(data_dir, {
                                'type': '买入',
                                'token': token_info.mint,
                                'token_name': token_info.name,
                                'token_symbol': token_info.symbol,
                                'amount': config['maxSolPerTrade'],
                                'status': '成功',
                                'hash': buy_tx,
                                'wallet': str(keypair.pubkey())
                            })

                            # Schedule sell after delay
                            if config['sellDelay'] > 0:
                                await asyncio.sleep(config['sellDelay'])
                                print('卖出')
                                await delayed_sell(token_info.mint, keypair, config['sellPercentage'])
                    else:
                        # Multi wallet mode
                        sell_tasks = []  # 用于存储所有的卖出任务
                        split_amount = config['maxSolPerTrade'] / len(wallets)

                        for wallet_pubkey in wallets:
                            keypair = wallet_manager.get_keypair(wallet_pubkey)
                            if not keypair:
                                print(f"Could not get keypair for wallet {wallet_pubkey}")
                                continue

                            success, buy_tx = buy_token(token_info.mint, keypair, split_amount, 5)
                            if success and buy_tx:
                                print(f"Buy transaction for wallet {wallet_pubkey}: https://solscan.io/tx/{buy_tx}")
                                save_transaction(data_dir, {
                                    'type': '买入',
                                    'token': token_info.mint,
                                    'token_name': token_info.name,
                                    'token_symbol': token_info.symbol,
                                    'amount': split_amount,
                                    'status': '成功',
                                    'hash': buy_tx,
                                    'wallet': str(keypair.pubkey())
                                })

                                # 为每个钱包创建延迟卖出任务
                                if config['sellDelay'] > 0:
                                    task = asyncio.create_task(
                                        delayed_sell(token_info.mint, keypair, config['sellPercentage']))
                                    sell_tasks.append(task)

                        # 等待所有卖出任务完成
                        if sell_tasks:
                            await asyncio.gather(*sell_tasks)

                except Exception as e:
                    print(f"Error handling token creation: {e}")
                    save_transaction(data_dir, {
                        'type': '买入',
                        'token': token_info.mint,
                        'token_name': token_info.name,
                        'token_symbol': token_info.symbol,
                        'amount': config['maxSolPerTrade'],
                        'status': '失败',
                        'error': str(e)
                    })

            async def delayed_sell(token_mint: str, keypair: Keypair, percentage: float):
                """Modified delayed sell function to use specific keypair"""
                with open(os.path.join(data_dir, "config.json"), 'r') as f:
                    config = json.load(f)

                try:
                    await asyncio.sleep(config['sellDelay'])
                    success, sell_tx = sell_token(token_mint, keypair, int(percentage))
                    if success and sell_tx:
                        print(f"Sell transaction for wallet {keypair.pubkey()}: https://solscan.io/tx/{sell_tx}")
                        save_transaction(data_dir, {
                            'type': '卖出',
                            'token': token_mint,
                            'amount': f"{percentage}%",
                            'status': '成功',
                            'hash': sell_tx,
                            'wallet': str(keypair.pubkey())
                        })
                except Exception as e:
                    print(f"Error in delayed sell: {e}")
                    save_transaction(data_dir, {
                        'type': '卖出',
                        'token': token_mint,
                        'amount': f"{percentage}%",
                        'status': '失败',
                        'error': str(e),
                        'wallet': str(keypair.pubkey())
                    })

            async def check_stop():
                while not stop_event.is_set():
                    await asyncio.sleep(1)

                # Clean up when stop event is set
                await monitor_manager.stop_monitoring()
                loop.stop()

            # Run both monitoring and stop checking concurrently
            loop.create_task(run_monitor())
            loop.create_task(check_stop())
            loop.run_forever()

        except Exception as e:
            print(f"Error in sniper process: {e}")
        finally:
            loop.close()

    def start(self):
        """Start the sniper in a new process"""
        if self.get_status():
            return False

        try:
            # Create and start the process
            self.stop_event.clear()
            self.process = Process(
                target=self.sniper_process,
                args=(self.stop_event, self.data_dir, self.monitor_manager, self.wallet_manager)
            )
            self.process.start()
            self.save_status(True)
            return True
        except Exception as e:
            print(f"Error starting sniper process: {e}")
            return False

    def stop(self):
        """Stop the sniper process"""
        if not self.get_status():
            return False

        try:
            # Signal the process to stop
            self.stop_event.set()

            # Wait for process to terminate
            if self.process:
                self.process.join(timeout=5)
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join()
                self.process = None

            self.save_status(False)
            return True
        except Exception as e:
            print(f"Error stopping sniper process: {e}")
            return False


def save_transaction(data_dir: str, tx_data: Dict):
    """Helper function to save transaction record"""
    transactions_file = os.path.join(data_dir, "transactions.json")
    try:
        with open(transactions_file, 'r') as f:
            transactions = json.load(f)
    except:
        transactions = []

    tx_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transactions.append(tx_data)

    with open(transactions_file, 'w') as f:
        json.dump(transactions, f, indent=2)
