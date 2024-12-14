from flask import Flask, jsonify, render_template, request
from datetime import datetime
import json

app = Flask(__name__)

# Simulated data structures
wallets = [
    {"address": "ABC123...", "balance": "10.5 SOL", "status": "Active"},
    {"address": "DEF456...", "balance": "5.2 SOL", "status": "Inactive"}
]

contract_filters = [
    {"address": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P", "enabled": True},
    {"address": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "enabled": False}
]

recent_transactions = [
    {
        "timestamp": "2024-12-10 10:30:15",
        "type": "Buy",
        "token": "TEST",
        "amount": "100",
        "status": "Success"
    }
]


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/start_sniper', methods=['POST'])
def start_sniper():
    data = request.json
    # Simulate starting sniper operation
    return jsonify({
        "status": "success",
        "message": "Sniper started successfully",
        "settings": data
    })


@app.route('/api/stop_sniper', methods=['POST'])
def stop_sniper():
    return jsonify({
        "status": "success",
        "message": "Sniper stopped successfully"
    })


@app.route('/api/add_wallet', methods=['POST'])
def add_wallet():
    wallet_data = request.json
    # Simulate adding wallet
    wallets.append({
        "address": wallet_data["address"],
        "balance": "0 SOL",
        "status": "Active"
    })
    return jsonify({"status": "success"})


@app.route('/api/get_wallets', methods=['GET'])
def get_wallets():
    return jsonify(wallets)


@app.route('/api/add_contract_filter', methods=['POST'])
def add_contract_filter():
    filter_data = request.json
    # Simulate adding contract filter
    contract_filters.append({
        "address": filter_data["address"],
        "enabled": True
    })
    return jsonify({"status": "success"})


@app.route('/api/remove_contract_filter', methods=['POST'])
def remove_contract_filter():
    filter_data = request.json
    # Simulate removing contract filter
    global contract_filters
    contract_filters = [f for f in contract_filters if f["address"] != filter_data["address"]]
    return jsonify({"status": "success"})


@app.route('/api/get_contract_filters', methods=['GET'])
def get_contract_filters():
    return jsonify(contract_filters)


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    return jsonify(recent_transactions)


if __name__ == '__main__':
    app.run(debug=True)
