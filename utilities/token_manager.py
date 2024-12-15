from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.types import TokenAccountOpts
from spl.token.instructions import get_associated_token_address, create_associated_token_account
from spl.token.constants import TOKEN_PROGRAM_ID
from typing import Optional, Dict
from .solana_client import SolanaClient


class TokenManager:
    def __init__(self):
        """Initialize TokenManager"""
        self.solana_client = SolanaClient()

    async def get_token_balance(self, wallet: str, token_mint: str) -> Optional[float]:
        """
        Get token balance for a specific wallet and token
        Args:
            wallet: Wallet public key string
            token_mint: Token mint address string
        Returns:
            Token balance or None if failed
        """
        try:
            token_account = get_associated_token_address(
                Pubkey.from_string(wallet),
                Pubkey.from_string(token_mint)
            )

            response = self.solana_client.client.get_token_account_balance(token_account)
            if response.value:
                return float(response.value.amount) / (10 ** response.value.decimals)
            return None
        except Exception as e:
            print(f"Error getting token balance: {e}")
            return None

    async def ensure_token_account(self, wallet: Keypair, token_mint: str) -> Optional[Pubkey]:
        """
        Ensure token account exists for wallet
        Args:
            wallet: Wallet keypair
            token_mint: Token mint address string
        Returns:
            Token account address if successful, None otherwise
        """
        try:
            mint_pubkey = Pubkey.from_string(token_mint)
            token_account = get_associated_token_address(wallet.pubkey(), mint_pubkey)

            # Check if account exists
            response = self.solana_client.client.get_account_info(token_account)
            if response.value is None:
                # Create associated token account
                create_account_ix = create_associated_token_account(
                    payer=wallet.pubkey(),
                    owner=wallet.pubkey(),
                    mint=mint_pubkey
                )

                # Send transaction
                # Note: Implement transaction sending here
                pass

            return token_account
        except Exception as e:
            print(f"Error ensuring token account: {e}")
            return None

    async def get_token_info(self, token_mint: str) -> Dict:
        """
        Get comprehensive token information
        Args:
            token_mint: Token mint address string
        Returns:
            Dict containing token information
        """
        try:
            # Get supply and decimals
            supply_info = self.solana_client.client.get_token_supply(
                Pubkey.from_string(token_mint)
            )

            # Get metadata if available
            metadata = await self.solana_client.get_token_metadata(token_mint)

            return {
                'mint': token_mint,
                'supply': supply_info.value.amount,
                'decimals': supply_info.value.decimals,
                'symbol': metadata.get('symbol', 'Unknown'),
                'name': metadata.get('name', 'Unknown Token')
            }
        except Exception as e:
            print(f"Error getting token info: {e}")
            return {
                'mint': token_mint,
                'supply': 0,
                'decimals': 0,
                'symbol': 'Unknown',
                'name': 'Unknown Token'
            }