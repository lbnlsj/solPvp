from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solders.compute_budget import set_compute_unit_price
from spl.token.instructions import (
    get_associated_token_address,
    create_associated_token_account,
    TransferCheckedParams,
    transfer_checked
)
from spl.token.constants import TOKEN_PROGRAM_ID
from solana.rpc.types import TxOpts
from typing import Optional, Dict
from .solana_client import SolanaClient


class TokenManager:
    def __init__(self):
        """Initialize TokenManager"""
        self.solana_client = SolanaClient()
        self.COMPUTE_UNIT_PRICE = 333333  # Standard compute unit price

    async def transfer_sol(self, from_keypair: Keypair, to_pubkey: Pubkey, amount: float) -> Dict:
        """
        Transfer SOL from one wallet to another

        Args:
            from_keypair: Sender's keypair
            to_pubkey: Recipient's public key
            amount: Amount of SOL to transfer

        Returns:
            Dict with transfer status and signature
        """
        try:
            # Convert SOL to lamports
            lamports = int(amount * 1e9)

            # Create transfer instruction
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=from_keypair.pubkey(),
                    to_pubkey=to_pubkey,
                    lamports=lamports
                )
            )

            # Set compute unit price instruction
            set_compute_price_ix = set_compute_unit_price(self.COMPUTE_UNIT_PRICE)

            # Get recent blockhash
            blockhash = self.solana_client.client.get_latest_blockhash().value.blockhash

            # Create and compile message
            msg = MessageV0.try_compile(
                payer=from_keypair.pubkey(),
                instructions=[set_compute_price_ix, transfer_ix],
                address_lookup_table_accounts=[],
                recent_blockhash=blockhash
            )

            # Create and sign transaction
            tx = VersionedTransaction(msg, [from_keypair])

            # Send transaction
            opt = TxOpts(skip_preflight=True)
            response = self.solana_client.client.send_transaction(tx, opt)

            return {
                "status": "success",
                "signature": str(response.value)
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    async def transfer_token(self, from_keypair: Keypair, to_pubkey: Pubkey, token_mint: str, amount: float) -> Dict:
        """
        Transfer SPL tokens from one wallet to another

        Args:
            from_keypair: Sender's keypair
            to_pubkey: Recipient's public key
            token_mint: Token mint address
            amount: Amount of tokens to transfer

        Returns:
            Dict with transfer status and signature
        """
        try:
            mint_pubkey = Pubkey.from_string(token_mint)

            # Get token accounts
            sender_token_account = get_associated_token_address(
                from_keypair.pubkey(),
                mint_pubkey
            )
            receiver_token_account = get_associated_token_address(
                to_pubkey,
                mint_pubkey
            )

            instructions = []

            # Add compute unit price instruction
            instructions.append(set_compute_unit_price(self.COMPUTE_UNIT_PRICE))

            # Check if receiver's token account exists
            receiver_account = self.solana_client.client.get_account_info(receiver_token_account)
            if receiver_account.value is None:
                # Create receiver's token account if it doesn't exist
                create_account_ix = create_associated_token_account(
                    payer=from_keypair.pubkey(),
                    owner=to_pubkey,
                    mint=mint_pubkey
                )
                instructions.append(create_account_ix)

            # Get token decimals
            mint_info = self.solana_client.client.get_token_supply(mint_pubkey)
            decimals = mint_info.value.decimals

            # Calculate amount in smallest units
            token_amount = int(amount * (10 ** decimals))

            # Create transfer instruction
            transfer_ix = transfer_checked(
                TransferCheckedParams(
                    program_id=TOKEN_PROGRAM_ID,
                    source=sender_token_account,
                    mint=mint_pubkey,
                    dest=receiver_token_account,
                    owner=from_keypair.pubkey(),
                    amount=token_amount,
                    decimals=decimals,
                    signers=[]
                )
            )
            instructions.append(transfer_ix)

            # Get recent blockhash
            blockhash = self.solana_client.client.get_latest_blockhash().value.blockhash

            # Create and compile message
            msg = MessageV0.try_compile(
                payer=from_keypair.pubkey(),
                instructions=instructions,
                address_lookup_table_accounts=[],
                recent_blockhash=blockhash
            )

            # Create and sign transaction
            tx = VersionedTransaction(msg, [from_keypair])

            # Send transaction
            opt = TxOpts(skip_preflight=True)
            response = self.solana_client.client.send_transaction(tx, opt)

            return {
                "status": "success",
                "signature": str(response.value)
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
