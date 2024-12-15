# utilities/transfer_handler.py
from typing import Dict, Optional
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from .wallet_manager import WalletManager
from .token_manager import TokenManager


class TransferHandler:
    def __init__(self, wallet_manager: WalletManager, token_manager: TokenManager):
        self.wallet_manager = wallet_manager
        self.token_manager = token_manager

    async def handle_collection(self, from_wallet: str, token_address: str, amount: float) -> Dict:
        """Handle fund collection from wallet to master wallet"""
        try:
            # Get source wallet keypair
            source_keypair = self.wallet_manager.get_keypair(from_wallet)
            if not source_keypair:
                return {"status": "error", "message": "Invalid source wallet"}

            # Get master wallet as target
            master_wallets = self.wallet_manager.get_all_pubkeys()
            if not master_wallets:
                return {"status": "error", "message": "No master wallet available"}
            master_pubkey = Pubkey.from_string(master_wallets[0])

            # Execute transfer
            if token_address.upper() == "SOL":
                return await self.token_manager.transfer_sol(
                    source_keypair,
                    master_pubkey,
                    amount
                )
            else:
                return await self.token_manager.transfer_token(
                    source_keypair,
                    master_pubkey,
                    token_address,
                    amount
                )

        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def handle_distribution(self, to_wallet: str, token_address: str, amount: float) -> Dict:
        """Handle fund distribution from master wallet to target wallet"""
        try:
            # Get master wallet keypair
            master_wallets = self.wallet_manager.get_all_pubkeys()
            if not master_wallets:
                return {"status": "error", "message": "No master wallet available"}

            master_keypair = self.wallet_manager.get_keypair(master_wallets[0])
            if not master_keypair:
                return {"status": "error", "message": "Invalid master wallet"}

            # Get target pubkey
            target_pubkey = Pubkey.from_string(to_wallet)

            # Execute transfer
            if token_address.upper() == "SOL":
                return await self.token_manager.transfer_sol(
                    master_keypair,
                    target_pubkey,
                    amount
                )
            else:
                return await self.token_manager.transfer_token(
                    master_keypair,
                    target_pubkey,
                    token_address,
                    amount
                )

        except Exception as e:
            return {"status": "error", "message": str(e)}
