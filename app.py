from flask import Flask, jsonify, render_template, request
from datetime import datetime
import json
import os

if not os.path.isdir('data'):
    os.mkdir('data')
import asyncio
from functools import wraps
from concurrent.futures import ThreadPoolExecutor

# Import utilities
from utilities.wallet_manager import WalletManager
from utilities.token_manager import TokenManager
from utilities.transfer_handler import TransferHandler
from utilities.monitor_manager import MonitorManager
from utilities.solana_client import SolanaClient
import logging


# 配置 Flask 日志
class NoRequestFilter(logging.Filter):
    def filter(self,record):
        return not (
                '/api/status' in record.getMessage() or
                '/api/transactions' in record.getMessage() or
                '/api/sniper/status' in record.getMessage()
            )


# 获取 Werkzeug 日志记录器并添加过滤器
logging.getLogger('werkzeug').addFilter(NoRequestFilter())

app = Flask(__name__)
logger = app.logger

exclude_access_log_filter = NoRequestFilter()
app.logger.addFilter(exclude_access_log_filter)

executor = ThreadPoolExecutor()
loop = None

# Configuration
DATA_DIR = "data"
RPC_URL = "https://staked.helius-rpc.com?api-key=bc8bd2ae-8330-4a02-9c98-2970d98545cd"

# Initialize managers
wallet_manager = WalletManager(DATA_DIR)
token_manager = TokenManager()
transfer_handler = TransferHandler(wallet_manager, token_manager)
monitor_manager = MonitorManager()
solana_client = SolanaClient(RPC_URL)

# File paths
CONTRACTS_FILE = os.path.join(DATA_DIR, "contracts.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.json")


def init_data_files():
    """Initialize necessary data files"""
    os.makedirs(DATA_DIR, exist_ok=True)

    default_files = {
        CONTRACTS_FILE: [],
        TRANSACTIONS_FILE: [],
        CONFIG_FILE: {
            "maxSolPerTrade": 0.0001,
            "gasFee": 1,
            "sellDelay": 0,
            "sellPercentage": 100
        }
    }

    for file_path, default_data in default_files.items():
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump(default_data, f, indent=2)


init_data_files()


def async_route(f):
    """Decorator for async route handlers with proper event loop handling"""

    @wraps(f)
    def wrapped(*args, **kwargs):
        # 获取当前的事件循环或创建新的
        global loop
        if loop is None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # 在事件循环中运行协程
        return loop.run_until_complete(f(*args, **kwargs))

    return wrapped


# 在导入部分添加
from utilities.sniper_manager import SniperManager

# 在 app 初始化后添加
sniper_manager = SniperManager(DATA_DIR, monitor_manager, wallet_manager)


# Modify these routes in app.py

@app.route('/api/start_sniper', methods=['POST'])
def start_sniper():
    try:
        config = request.json
        save_data(config, CONFIG_FILE)

        if sniper_manager.start():
            return jsonify({
                "status": "success",
                "message": "Sniper started successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Sniper is already running"
            }), 400
    except Exception as e:
        print(f"Error starting sniper: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/stop_sniper', methods=['POST'])
def stop_sniper():
    try:
        if sniper_manager.stop():
            return jsonify({
                "status": "success",
                "message": "Sniper stopped successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Sniper is not running"
            }), 400
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# Update the cleanup function
def cleanup():
    if sniper_manager.get_status():
        sniper_manager.stop()


@app.route('/api/sniper/status', methods=['GET'])
def get_sniper_status():
    """Get current sniper status"""
    status = sniper_manager.get_status()
    return jsonify({
        "status": "success",
        "is_running": status
    })


def load_data(file_path):
    """Load JSON data from file"""
    with open(file_path, 'r') as f:
        return json.load(f)


def save_data(data, file_path):
    """Save JSON data to file"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def save_transaction(tx_data):
    """Save transaction record"""
    transactions = load_data(TRANSACTIONS_FILE)
    tx_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transactions.append(tx_data)
    save_data(transactions, TRANSACTIONS_FILE)


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/wallets', methods=['GET', 'POST', 'DELETE'])
def manage_wallets():
    if request.method == 'GET':
        return jsonify(wallet_manager.get_all_pubkeys())

    elif request.method == 'POST':
        private_key = request.json.get('address')
        if not private_key:
            return jsonify({"status": "error", "message": "Private key required"}), 400

        pubkey = wallet_manager.add_wallet(private_key)
        if pubkey:
            return jsonify({"status": "success", "pubkey": pubkey})
        return jsonify({"status": "error", "message": "Invalid private key"}), 400

    elif request.method == 'DELETE':
        if address := request.args.get('address'):
            if wallet_manager.remove_wallet(address):
                return jsonify({"status": "success"})
            return jsonify({"status": "error", "message": "Wallet not found"}), 404
        else:
            wallet_manager.clear_all_wallets()
            return jsonify({"status": "success"})


@app.route('/api/collect_funds', methods=['POST'])
@async_route
async def collect_funds():
    data = request.json
    if not all(k in data for k in ['walletAddress', 'tokenAddress', 'amount']):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    result = await transfer_handler.handle_collection(
        data['walletAddress'],
        data['tokenAddress'],
        float(data['amount'])
    )

    if result['status'] == 'success':
        for signature in result['successful_transfers']:
            save_transaction({
                'type': '归集',
                'token': data['tokenAddress'],
                'amount': data['amount'],
                'status': '成功',
                'hash': signature
            })

    return jsonify(result)


@app.route('/api/distribute_funds', methods=['POST'])
@async_route
async def distribute_funds():
    data = request.json
    if not all(k in data for k in ['walletAddress', 'tokenAddress', 'amount']):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    result = await transfer_handler.handle_distribution(
        data['walletAddress'],
        data['tokenAddress'],
        float(data['amount'])
    )

    if result['status'] == 'success':
        for signature in result['successful_transfers']:
            save_transaction({
                'type': '分发',
                'token': data['tokenAddress'],
                'amount': data['amount'],
                'status': '成功',
                'hash': signature
            })

    return jsonify(result)


@app.route('/api/contracts', methods=['GET', 'POST', 'DELETE'])
def manage_contracts():
    if request.method == 'GET':
        return jsonify(load_data(CONTRACTS_FILE))

    elif request.method == 'POST':
        contracts = load_data(CONTRACTS_FILE)
        new_contract = request.json.get('address')
        if new_contract and new_contract not in contracts:
            contracts.append(new_contract)
            save_data(contracts, CONTRACTS_FILE)
        return jsonify({"status": "success"})

    elif request.method == 'DELETE':
        if address := request.args.get('address'):
            contracts = load_data(CONTRACTS_FILE)
            if address in contracts:
                contracts.remove(address)
                save_data(contracts, CONTRACTS_FILE)
                return jsonify({"status": "success"})
            return jsonify({"status": "error", "message": "Contract not found"}), 404
        else:
            save_data([], CONTRACTS_FILE)
            return jsonify({"status": "success"})


@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    if request.method == 'GET':
        return jsonify(load_data(CONFIG_FILE))

    elif request.method == 'POST':
        config = request.json
        save_data(config, CONFIG_FILE)
        return jsonify({"status": "success"})


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    return jsonify(load_data(TRANSACTIONS_FILE))


if __name__ == '__main__':
    try:
        app.run(debug=True, port=9488, host='0.0.0.0')
    finally:
        cleanup()
