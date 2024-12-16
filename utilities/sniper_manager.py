# utilities/sniper_manager.py
from .monitor_manager import MonitorManager, TokenCreationInfo
from .wallet_manager import WalletManager
from datetime import datetime
import asyncio
from typing import Optional, Dict, Tuple
import json
import os
from .pump import buy_token, sell_token
import threading
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
        self.stop_event = threading.Event()
        self.thread = None
        self.sniper_is_running = False

        # 初始化状态文件如果不存在
        if not os.path.exists(self.status_file):
            self.save_status(False)

    def save_status(self, is_running: bool):
        self.sniper_is_running = is_running

    def get_status(self) -> bool:
        return self.sniper_is_running

    @staticmethod
    def sniper_thread_func(stop_event: threading.Event, data_dir: str, monitor_manager: MonitorManager,
                           wallet_manager: WalletManager):
        """
        运行在单独线程中的主函数
        """
        try:
            # 为这个线程创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def handle_token_creation(token_info: TokenCreationInfo, creation_tx: str):
                try:
                    # 加载配置
                    with open(os.path.join(data_dir, "config.json"), 'r') as f:
                        config = json.load(f)

                    with open(os.path.join(data_dir, "contracts.json"), 'r') as f:
                        contracts = json.load(f)

                    # 检查是否应该监控这个代币
                    # if contracts and token_info.mint not in contracts:
                    #     return

                    # 获取可用钱包
                    wallets = wallet_manager.get_all_pubkeys()
                    if not wallets:
                        print("没有可用钱包")
                        return

                    print(f"检测到新代币: {token_info.name} ({token_info.symbol})")
                    print(f"代币铸造地址: {token_info.mint}")
                    print(f"创建交易: https://solscan.io/tx/{creation_tx}\n")

                    if config['mode'] == 'single':
                        # 获取第一个钱包的密钥对
                        keypair = wallet_manager.get_keypair(wallets[0])
                        if not keypair:
                            print("无法获取钱包密钥对")
                            return

                        success, buy_tx = buy_token(token_info.mint, keypair, config['maxSolPerTrade'], 5)
                        if success and buy_tx:
                            # print(f"买入交易: https://solscan.io/tx/{buy_tx}")
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

                            # 延迟卖出
                            if config['sellDelay'] > 0:
                                await asyncio.sleep(config['sellDelay'])
                                print('卖出')
                                await delayed_sell(token_info.mint, keypair, config['sellPercentage'])
                    else:
                        # 多钱包模式
                        sell_tasks = []  # 存储所有卖出任务
                        split_amount = config['maxSolPerTrade'] / len(wallets)

                        for wallet_pubkey in wallets:
                            keypair = wallet_manager.get_keypair(wallet_pubkey)
                            if not keypair:
                                print(f"无法获取钱包密钥对 {wallet_pubkey}")
                                continue

                            success, buy_tx = buy_token(token_info.mint, keypair, split_amount, 5)
                            if success and buy_tx:
                                print(f"钱包 {wallet_pubkey} 的买入交易: https://solscan.io/tx/{buy_tx}")
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
                    print(f"处理代币创建时出错: {e}")
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
                with open(os.path.join(data_dir, "config.json"), 'r') as f:
                    config = json.load(f)

                try:
                    await asyncio.sleep(config['sellDelay'])
                    success, sell_tx = sell_token(token_mint, keypair, int(percentage))
                    if success and sell_tx:
                        print(f"钱包 {keypair.pubkey()} 的卖出交易: https://solscan.io/tx/{sell_tx}")
                        save_transaction(data_dir, {
                            'type': '卖出',
                            'token': token_mint,
                            'amount': f"{percentage}%",
                            'status': '成功',
                            'hash': sell_tx,
                            'wallet': str(keypair.pubkey())
                        })
                except Exception as e:
                    print(f"延迟卖出时出错: {e}")
                    save_transaction(data_dir, {
                        'type': '卖出',
                        'token': token_mint,
                        'amount': f"{percentage}%",
                        'status': '失败',
                        'error': str(e),
                        'wallet': str(keypair.pubkey())
                    })

            async def run_monitor():
                # monitor_manager.add_callback(handle_token_creation)
                program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
                await monitor_manager.start_monitoring(program_id)
                # try:
                #     # 添加代币创建事件的回调
                #     monitor_manager.add_callback(handle_token_creation)
                #
                #     # 开始监控
                #     program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
                #     await monitor_manager.start_monitoring(program_id)
                # except Exception as e:
                #     print(f"监控线程出错error: {e}")
                #     stop_event.set()

            async def check_stop():
                while not stop_event.is_set():
                    await asyncio.sleep(1)

                # 当收到停止信号时清理
                await monitor_manager.stop_monitoring()
                loop.stop()

            # 并发运行监控和停止检查
            loop.create_task(run_monitor())
            # loop.create_task(check_stop())
            loop.run_forever()

        except Exception as e:
            print(f"狙击线程出错error: {e}")
        finally:
            loop.close()

    def start(self):
        """启动狙击器线程"""
        if self.get_status():
            return False

        try:
            # 创建并启动线程
            self.stop_event.clear()
            self.thread = threading.Thread(
                target=self.sniper_thread_func,
                args=(self.stop_event, self.data_dir, self.monitor_manager, self.wallet_manager),
                daemon=False
            )
            self.thread.start()
            self.save_status(True)
            return True
        except Exception as e:
            print(f"启动狙击线程时出错: {e}")
            return False

    def stop(self):
        """停止狙击器线程"""
        self.monitor_manager.is_running = False
        if not self.get_status():
            return False

        self.save_status(False)
        return True


def save_transaction(data_dir: str, tx_data: Dict):
    """保存交易记录的辅助函数"""
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