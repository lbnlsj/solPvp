import traceback
import time
import os
import json
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.instruction import Instruction
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solana.rpc.types import TokenAccountOpts, TxOpts
from spl.token.instructions import get_associated_token_address, create_associated_token_account
import struct
from solana.transaction import AccountMeta
from dataclasses import dataclass
from typing import Optional, Tuple

# Constants
GLOBAL = Pubkey.from_string("4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf")
FEE_RECIPIENT = Pubkey.from_string("CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM")
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
PUMP_FUN_PROGRAM = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
RENT = Pubkey.from_string("SysvarRent111111111111111111111111111111111")
EVENT_AUTHORITY = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")
ASSOC_TOKEN_ACC_PROG = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")

# Configuration
RPC_URL = "https://staked.helius-rpc.com?api-key=bc8bd2ae-8330-4a02-9c98-2970d98545cd"
UNIT_BUDGET = 100_000
UNIT_PRICE = 333_333

client = Client(RPC_URL)


@dataclass
class CoinData:
    mint: Pubkey
    bonding_curve: Pubkey
    associated_bonding_curve: Pubkey
    virtual_token_reserves: int
    virtual_sol_reserves: int
    complete: bool


def get_coin_data(mint_str: str) -> Optional[CoinData]:
    """
    Get coin data from the blockchain
    Args:
        mint_str: Token mint address
    Returns:
        CoinData object if successful, None otherwise
    """

    try:
        mint = Pubkey.from_string(mint_str)

        # Derive bonding curve address
        bonding_curve, _ = Pubkey.find_program_address(
            ["bonding-curve".encode(), bytes(mint)],
            PUMP_FUN_PROGRAM
        )

        # Get associated token account
        associated_bonding_curve = get_associated_token_address(bonding_curve, mint)

        # Get account info
        account_info = client.get_account_info(bonding_curve)
        if not account_info:
            return None

        if not account_info.value:
            time.sleep(1)
            return get_coin_data(mint_str)
        else:

            # Parse account data
            data = account_info.value.data
            virtual_token_reserves = int.from_bytes(data[8:16], 'little')
            virtual_sol_reserves = int.from_bytes(data[16:24], 'little')
            complete = bool(data[-1])

        return CoinData(
            mint=mint,
            bonding_curve=bonding_curve,
            associated_bonding_curve=associated_bonding_curve,
            virtual_token_reserves=virtual_token_reserves,
            virtual_sol_reserves=virtual_sol_reserves,
            complete=complete
        )
    except Exception as e:
        print(f"get_coin_data error: {e}")
        return None


def buy_token(mint_str: str, keypair: Keypair, sol_amount: float = 0.01, slippage: int = 5) -> Tuple[
    bool, Optional[str]]:
    """
    Buy token from the Pump.fun platform
    Args:
        mint_str: Token mint address
        keypair: Keypair of the buyer
        sol_amount: Amount of SOL to spend
        slippage: Slippage tolerance percentage
    Returns:
        Tuple of (success: bool, transaction_signature: Optional[str])
    """
    try:
        print(f"Buying token {mint_str} with wallet {keypair.pubkey()}")
        # ... 其他代码保持不变，但把所有 keypair 替换为 keypair ...

        # Get coin data
        coin_data = get_coin_data(mint_str)
        if not coin_data:
            print("Invalid token or token has completed bonding")
            return False, None

        # Calculate amounts
        sol_lamports = int(sol_amount * 1e18)  # Convert to lamports
        amount = sol_lamports
        slippage_adjusted = int(sol_lamports * (1 + slippage / 100))

        print(f"Amount (lamports): {amount}")
        print(f"Max sol cost (lamports): {slippage_adjusted}")
        print(f"Virtual sol reserves: {coin_data.virtual_sol_reserves}")
        print(f"Virtual token reserves: {coin_data.virtual_token_reserves}")

        # Get or create associated token account
        user_ata = get_associated_token_address(keypair.pubkey(), coin_data.mint)
        create_ata_ix = None

        # try:
        #     client.get_token_accounts_by_owner(keypair.pubkey(), TokenAccountOpts(coin_data.mint))
        # except:
        #     create_ata_ix = create_associated_token_account(
        #         keypair.pubkey(),
        #         keypair.pubkey(),
        #         coin_data.mint
        #     )
        create_ata_ix = create_associated_token_account(
            keypair.pubkey(),
            keypair.pubkey(),
            coin_data.mint
        )

        # Create account metas
        keys = [
            AccountMeta(pubkey=GLOBAL, is_signer=False, is_writable=False),
            AccountMeta(pubkey=FEE_RECIPIENT, is_signer=False, is_writable=True),
            AccountMeta(pubkey=coin_data.mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=coin_data.bonding_curve, is_signer=False, is_writable=True),
            AccountMeta(pubkey=coin_data.associated_bonding_curve, is_signer=False, is_writable=True),
            AccountMeta(pubkey=user_ata, is_signer=False, is_writable=True),
            AccountMeta(pubkey=keypair.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=TOKEN_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=RENT, is_signer=False, is_writable=False),
            AccountMeta(pubkey=EVENT_AUTHORITY, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_FUN_PROGRAM, is_signer=False, is_writable=False)
        ]

        # Create instruction data
        data = bytearray(bytes.fromhex("66063d1201daebea"))  # buy instruction discriminator
        data.extend(struct.pack("<Q",
                                int(coin_data.virtual_token_reserves / coin_data.virtual_sol_reserves * 10 ** 10 * amount / 10e18)))
        data.extend(struct.pack("<Q", int(amount * 1.1)))

        # Create swap instruction
        swap_ix = Instruction(PUMP_FUN_PROGRAM, bytes(data), keys)

        with open(os.path.join('data', "config.json"), 'r') as f:
            config = json.load(f)

        # Create instructions list
        instructions = [
            set_compute_unit_limit(UNIT_BUDGET),
            set_compute_unit_price(UNIT_PRICE * config['gasFee'])
        ]

        if create_ata_ix:
            instructions.append(create_ata_ix)
        instructions.append(swap_ix)

        # Get recent blockhash
        blockhash = client.get_latest_blockhash().value.blockhash

        # Create and compile message
        message = MessageV0.try_compile(
            keypair.pubkey(),
            instructions,
            [],
            blockhash
        )

        # Create and sign transaction
        tx = VersionedTransaction(message, [keypair])

        # Send transaction
        sig = client.send_transaction(tx, opts=TxOpts(skip_preflight=True)).value
        print(f"Buy transaction sent: {sig}")

        return True, str(sig)

    except Exception as e:
        print(f"Error during buy: {e}")
        return False, None


def sell_token(mint_str: str, keypair: Keypair, percentage: int = 100, slippage: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Sell token on the Pump.fun platform
    Args:
        mint_str: Token mint address
        keypair: Keypair of the seller
        percentage: Percentage of tokens to sell (0-100)
        slippage: Slippage tolerance percentage
    Returns:
        Tuple of (success: bool, transaction_signature: Optional[str])
    """
    try:
        print(f"Selling {percentage}% of token {mint_str}")
        print(f"Slippage: {slippage}%")

        # Get coin data
        coin_data = get_coin_data(mint_str)
        if not coin_data:
            print("Invalid token or token has completed bonding")
            return False, None

        # Get token balance
        user_ata = get_associated_token_address(keypair.pubkey(), coin_data.mint)
        token_account = client.get_token_accounts_by_owner(
            keypair.pubkey(),
            TokenAccountOpts(coin_data.mint)
        ).value
        if len(token_account) == 0:
            return sell_token(mint_str, keypair, percentage, slippage)
        else:
            token_account = token_account[0]

        # Calculate amount to sell
        data = token_account.account.data
        balance = int.from_bytes(data[64:72], 'little')
        amount = int(balance * percentage / 100)

        if amount == 0:
            print("No tokens to sell")
            return False, None

        # Calculate minimum SOL output
        virtual_sol = coin_data.virtual_sol_reserves / 1e9
        virtual_tokens = coin_data.virtual_token_reserves / 1e6
        expected_sol = (virtual_sol * amount) / (virtual_tokens + amount)
        min_sol = int(expected_sol * (1 - slippage / 100) * 1e9)

        print(f"Amount to sell: {amount}")
        print(f"Expected SOL: {expected_sol}")
        print(f"Minimum SOL: {min_sol}")

        # Create account metas
        keys = [
            AccountMeta(pubkey=GLOBAL, is_signer=False, is_writable=False),
            AccountMeta(pubkey=FEE_RECIPIENT, is_signer=False, is_writable=True),
            AccountMeta(pubkey=coin_data.mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=coin_data.bonding_curve, is_signer=False, is_writable=True),
            AccountMeta(pubkey=coin_data.associated_bonding_curve, is_signer=False, is_writable=True),
            AccountMeta(pubkey=user_ata, is_signer=False, is_writable=True),
            AccountMeta(pubkey=keypair.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=ASSOC_TOKEN_ACC_PROG, is_signer=False, is_writable=False),
            AccountMeta(pubkey=TOKEN_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=EVENT_AUTHORITY, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_FUN_PROGRAM, is_signer=False, is_writable=False)
        ]

        # Create instruction data
        data = bytearray(bytes.fromhex("33e685a4017f83ad"))  # sell instruction discriminator
        data.extend(struct.pack("<Q", amount))
        data.extend(struct.pack("<Q", 1))

        # Create swap instruction
        swap_ix = Instruction(PUMP_FUN_PROGRAM, bytes(data), keys)

        # Get recent blockhash
        blockhash = client.get_latest_blockhash().value.blockhash

        with open(os.path.join('data', "config.json"), 'r') as f:
            config = json.load(f)

        # Create and compile message
        message = MessageV0.try_compile(
            keypair.pubkey(),
            [
                set_compute_unit_limit(UNIT_BUDGET),
                set_compute_unit_price(UNIT_PRICE * config['gasFee']),
                swap_ix
            ],
            [],
            blockhash
        )

        # Create and sign transaction
        tx = VersionedTransaction(message, [keypair])

        # Send transaction
        sig = client.send_transaction(tx, opts=TxOpts(skip_preflight=True)).value
        print(f"Sell transaction sent: {sig}")

        return True, str(sig)

    except Exception as e:
        print(f"Error during sell: {e}")
        traceback.print_exc()
        return sell_token(mint_str, keypair, percentage, slippage)
        # return False, None


# Example usage
if __name__ == "__main__":
    # Buy example
    # success, tx = buy_token("HAReKWhADs64eS18eB75LiU8UhkBkLmsauS475kjpump", 0.001, 5)
    # if success:
    #     print(f"Buy successful: {tx}")

    # Sell example
    # success, tx = sell_token("HAReKWhADs64eS18eB75LiU8UhkBkLmsauS475kjpump", 50, 5)
    # if success:
    #     print(f"Sell successful: {tx}")
    pass
