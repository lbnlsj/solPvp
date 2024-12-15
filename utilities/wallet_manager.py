# utilities/wallet_manager.py
from solders.keypair import Keypair
from solders.pubkey import Pubkey
import json
import os
import base58
from cryptography.fernet import Fernet
from .solana_client import SolanaClient
from typing import Optional, Dict, List


class WalletManager:
    def __init__(self, data_dir: str, encryption_key: Optional[str] = None):
        self.wallets_file = os.path.join(data_dir, "wallets.json")
        self.key_file = os.path.join(data_dir, "encryption.key")
        self.solana_client = SolanaClient()

        # Initialize encryption
        self._init_encryption(encryption_key)
        self._ensure_wallet_file()

    def _init_encryption(self, encryption_key: Optional[str]):
        if os.path.exists(self.key_file) and not encryption_key:
            with open(self.key_file, 'rb') as f:
                self.encryption_key = f.read()
        else:
            self.encryption_key = encryption_key.encode() if encryption_key else Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(self.encryption_key)

        self.cipher_suite = Fernet(self.encryption_key)

    def _ensure_wallet_file(self):
        if not os.path.exists(self.wallets_file):
            os.makedirs(os.path.dirname(self.wallets_file), exist_ok=True)
            with open(self.wallets_file, 'w') as f:
                json.dump({}, f)

    def add_wallet(self, private_key: str) -> Optional[str]:
        try:
            # Handle different private key formats
            if private_key.startswith('[') and private_key.endswith(']'):
                # Convert string array to bytes
                key_array = json.loads(private_key)
                secret_key_bytes = bytes(key_array)
                keypair = Keypair.from_bytes(secret_key_bytes)
            else:
                # Assume base58 encoded private key
                decoded_key = base58.b58decode(private_key)
                keypair = Keypair.from_bytes(decoded_key)

            # Get public key
            pubkey = str(keypair.pubkey())

            # Encrypt private key
            encrypted_key = self.cipher_suite.encrypt(bytes(keypair)).decode('utf-8')

            # Save wallet info
            wallets = self._load_wallets()
            wallets[pubkey] = encrypted_key
            self._save_wallets(wallets)

            return pubkey
        except Exception as e:
            print(f"Error adding wallet: {e}")
            return None

    def get_keypair(self, pubkey: str) -> Optional[Keypair]:
        try:
            wallets = self._load_wallets()
            if pubkey not in wallets:
                return None

            # Decrypt private key
            encrypted_key = wallets[pubkey]
            keypair_bytes = self.cipher_suite.decrypt(encrypted_key.encode())
            return Keypair.from_bytes(keypair_bytes)
        except Exception as e:
            print(f"Error getting keypair: {e}")
            return None

    def remove_wallet(self, pubkey: str) -> bool:
        try:
            wallets = self._load_wallets()
            if pubkey in wallets:
                del wallets[pubkey]
                self._save_wallets(wallets)
                return True
            return False
        except:
            return False

    def get_all_pubkeys(self) -> List[str]:
        return list(self._load_wallets().keys())

    def clear_all_wallets(self):
        self._save_wallets({})

    def _load_wallets(self) -> Dict[str, str]:
        try:
            with open(self.wallets_file, 'r') as f:
                return json.load(f)
        except:
            return {}

    def _save_wallets(self, wallets: Dict[str, str]):
        with open(self.wallets_file, 'w') as f:
            json.dump(wallets, f, indent=2)





