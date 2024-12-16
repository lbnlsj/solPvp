from typing import Dict, Optional, List
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from .wallet_manager import WalletManager
from .token_manager import TokenManager
import json
import os
from datetime import datetime


class TransferHandler:
    def __init__(self, wallet_manager: WalletManager, token_manager: TokenManager):
        """
        Initialize TransferHandler
        Args:
            wallet_manager: Instance of WalletManager
            token_manager: Instance of TokenManager
        """
        self.wallet_manager = wallet_manager
        self.token_manager = token_manager
        self.transactions_file = os.path.join("data", "transactions.json")

    def _save_transaction(self, tx_data: Dict):
        """Save transaction record to file"""
        try:
            if os.path.exists(self.transactions_file):
                with open(self.transactions_file, 'r') as f:
                    transactions = json.load(f)
            else:
                transactions = []

            tx_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            transactions.append(tx_data)

            with open(self.transactions_file, 'w') as f:
                json.dump(transactions, f, indent=2)

        except Exception as e:
            print(f"Error saving transaction: {e}")

    async def handle_collection(self, to_wallet: str, token_address: str, amount: float) -> Dict:
        """
        Handle fund collection from all other wallets to a single target wallet
        Args:
            to_wallet: Target wallet address to collect funds into
            token_address: Token address or "SOL"
            amount: Amount to collect from each wallet
        Returns:
            Dict with transfer status and details
        """
        try:
            # Get all wallets
            all_wallets = self.wallet_manager.get_all_pubkeys()
            if not all_wallets:
                return {"status": "error", "message": "No wallets available"}

            # Get target wallet pubkey
            target_pubkey = Pubkey.from_string(to_wallet)

            # Filter out source wallets (exclude target wallet)
            source_wallets = [w for w in all_wallets if w != to_wallet]
            if not source_wallets:
                return {"status": "error", "message": "No source wallets available"}

            successful_transfers = []
            failed_transfers = []
            transfer_details = []

            # Transfer from each source wallet
            for source_wallet in source_wallets:
                try:
                    # Get source wallet keypair
                    source_keypair = self.wallet_manager.get_keypair(source_wallet)
                    if not source_keypair:
                        failed_transfers.append({
                            "wallet": source_wallet,
                            "error": "Invalid wallet keypair"
                        })
                        continue

                    # Execute transfer
                    if token_address.upper() == "SOL":
                        result = await self.token_manager.transfer_sol(
                            source_keypair,
                            target_pubkey,
                            amount
                        )
                    else:
                        result = await self.token_manager.transfer_token(
                            source_keypair,
                            target_pubkey,
                            token_address,
                            amount
                        )

                    # Record transfer result
                    transfer_detail = {
                        "type": "归集",
                        "from": source_wallet,
                        "to": to_wallet,
                        "token": token_address,
                        "amount": amount,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    if result["status"] == "success":
                        transfer_detail.update({
                            "status": "成功",
                            "signature": result["signature"]
                        })
                        successful_transfers.append(result["signature"])
                    else:
                        transfer_detail.update({
                            "status": "失败",
                            "error": result.get("message", "Unknown error")
                        })
                        failed_transfers.append({
                            "wallet": source_wallet,
                            "error": result.get("message")
                        })

                    transfer_details.append(transfer_detail)

                except Exception as e:
                    failed_transfers.append({
                        "wallet": source_wallet,
                        "error": str(e)
                    })

            # Save all transfer records
            # for detail in transfer_details:
            #     self._save_transaction(detail)

            # Generate summary message
            summary = f"Successfully collected from {len(successful_transfers)} out of {len(source_wallets)} wallets"
            if failed_transfers:
                summary += f"\nFailed transfers ({len(failed_transfers)}):"
                for failure in failed_transfers:
                    summary += f"\n- {failure['wallet']}: {failure['error']}"

            return {
                "status": "success" if successful_transfers else "error",
                "successful_transfers": successful_transfers,
                "failed_transfers": failed_transfers,
                "transfer_details": transfer_details,
                "message": summary
            }

        except Exception as e:
            error_msg = f"Error during collection: {str(e)}"
            return {
                "status": "error",
                "message": error_msg,
                "successful_transfers": [],
                "failed_transfers": [],
                "transfer_details": []
            }

    async def handle_distribution(self, to_wallet: str, token_address: str, amount: float) -> Dict:
        """
        Handle fund distribution from one wallet to all other wallets
        Args:
            to_wallet: Source wallet for distribution
            token_address: Token address or "SOL"
            amount: Amount to distribute to each wallet
        Returns:
            Dict with transfer status and details
        """
        try:
            # Get source wallet keypair
            source_keypair = self.wallet_manager.get_keypair(to_wallet)
            if not source_keypair:
                return {"status": "error", "message": "Invalid source wallet"}

            # Get all other wallets except source
            all_wallets = self.wallet_manager.get_all_pubkeys()
            target_wallets = [w for w in all_wallets if w != to_wallet]

            if not target_wallets:
                return {"status": "error", "message": "No target wallets available"}

            successful_transfers = []
            failed_transfers = []

            # Calculate amount per wallet
            amount_per_wallet = amount

            # Distribute to each target wallet
            for target_wallet in target_wallets:
                target_pubkey = Pubkey.from_string(target_wallet)

                # Execute transfer
                if token_address.upper() == "SOL":
                    result = await self.token_manager.transfer_sol(
                        source_keypair,
                        target_pubkey,
                        amount_per_wallet
                    )
                else:
                    result = await self.token_manager.transfer_token(
                        source_keypair,
                        target_pubkey,
                        token_address,
                        amount_per_wallet
                    )

                # Save transaction record
                tx_data = {
                    "type": "分发",
                    "from": str(source_keypair.pubkey()),
                    "to": target_wallet,
                    "token": token_address,
                    "amount": amount_per_wallet,
                }

                if result["status"] == "success":
                    tx_data.update({
                        "status": "成功",
                        "hash": result["signature"]
                    })
                    successful_transfers.append(result["signature"])
                else:
                    tx_data.update({
                        "status": "失败",
                        "error": result.get("message", "Unknown error")
                    })
                    failed_transfers.append(target_wallet)

                # self._save_transaction(tx_data)

            # Return summary
            return {
                "status": "success" if successful_transfers else "error",
                "successful_transfers": successful_transfers,
                "failed_transfers": failed_transfers,
                "message": f"Successfully distributed to {len(successful_transfers)} wallets, {len(failed_transfers)} failed"
            }

        except Exception as e:
            error_msg = str(e)
            return {"status": "error", "message": error_msg}
