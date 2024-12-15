from flask import Flask, jsonify, render_template, request
from datetime import datetime
import json
import os
import asyncio
from functools import wraps

# Import utilities
from utilities.wallet_manager import WalletManager
from utilities.token_manager import TokenManager
from utilities.transfer_handler import TransferHandler
from utilities.monitor_manager import MonitorManager
from utilities.solana_client import SolanaClient

app = Flask(__name__)

# Configuration
DATA_DIR = "data"
RPC_URL = "https://staked.helius-rpc.com?api-key=bc8bd2ae-8330-4a02-9c98-2970d98545cd"

# Initialize managers
wallet_manager = WalletManager(DATA_DIR)
token_manager = TokenManager()
transfer_handler = TransferHandler(wallet_manager, token_manager)
monitor_manager = MonitorManager(RPC_URL)
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
            "maxSolPerTrade": 1.0,
            "gasFee": 1,
            "sellDelay": 5,
            "sellPercentage": 50
        }
    }

    for file_path, default_data in default_files.items():
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump(default_data, f, indent=2)


init_data_files()


def async_route(f):
    """Decorator for async route handlers"""

    @wraps(f)
    def wrapped(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapped


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
        save_transaction({
            'type': '归集',
            'token': data['tokenAddress'],
            'amount': data['amount'],
            'status': '成功',
            'hash': result['signature']
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
        save_transaction({
            'type': '分发',
            'token': data['tokenAddress'],
            'amount': data['amount'],
            'status': '成功',
            'hash': result['signature']
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


@app.route('/api/start_sniper', methods=['POST'])
@async_route
async def start_sniper():
    try:
        config = request.json
        save_data(config, CONFIG_FILE)

        # Start monitoring
        await monitor_manager.start_monitoring()
        return jsonify({"status": "success", "message": "Sniper started successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/stop_sniper', methods=['POST'])
@async_route
async def stop_sniper():
    try:
        await monitor_manager.stop_monitoring()
        return jsonify({"status": "success", "message": "Sniper stopped successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)