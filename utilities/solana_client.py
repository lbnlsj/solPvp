from solana.rpc.api import Client
from solders.pubkey import Pubkey
from solana.rpc.types import TokenAccountOpts
from typing import Optional, List, Dict
import asyncio


class SolanaClient:
    def __init__(self, rpc_url: Optional[str] = None):
        """
        Initialize Solana client
        Args:
            rpc_url: Custom RPC URL, uses default if None
        """
        self.rpc_url = rpc_url or "https://staked.helius-rpc.com?api-key=bc8bd2ae-8330-4a02-9c98-2970d98545cd"
        self.client = Client(self.rpc_url)

    async def get_balance(self, pubkey: str) -> Optional[float]:
        """
        Get SOL balance for address
        Args:
            pubkey: Public key string
        Returns:
            Balance in SOL or None if failed
        """
        try:
            response = self.client.get_balance(Pubkey.from_string(pubkey))
            if response.value is not None:
                return response.value / 1e9
            return None
        except Exception as e:
            print(f"Error getting balance: {e}")
            return None

    async def get_token_accounts(self, pubkey: str) -> List[Dict]:
        """
        Get all token accounts for address
        Args:
            pubkey: Public key string
        Returns:
            List of token account information
        """
        try:
            response = self.client.get_token_accounts_by_owner(
                Pubkey.from_string(pubkey),
                TokenAccountOpts()
            )

            token_accounts = []
            for account in response.value:
                data = account.account.data
                mint = str(Pubkey.from_bytes(data[0:32]))
                amount = int.from_bytes(data[64:72], 'little')
                decimals = data[44]

                # Get token metadata if available
                try:
                    token_info = await self.get_token_metadata(mint)
                except:
                    token_info = {'symbol': 'Unknown', 'name': 'Unknown Token'}

                token_accounts.append({
                    'mint': mint,
                    'amount': amount / (10 ** decimals),
                    'decimals': decimals,
                    'symbol': token_info.get('symbol', 'Unknown'),
                    'name': token_info.get('name', 'Unknown Token')
                })

            return token_accounts
        except Exception as e:
            print(f"Error getting token accounts: {e}")
            return []

    async def get_token_metadata(self, mint: str) -> Dict:
        """
        Get token metadata
        Args:
            mint: Token mint address
        Returns:
            Dict containing token metadata
        """
        # Note: Implement token metadata fetching here
        # This could involve calling Metaplex or other metadata services
        return {
            'symbol': 'Unknown',
            'name': 'Unknown Token'
        }