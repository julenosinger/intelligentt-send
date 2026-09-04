"""Utility script to inspect the GenLayer Bradbury network state."""
import os

from dotenv import load_dotenv

load_dotenv()


def inspect_bradbury():
    """Inspect the Bradbury GenLayer network."""
    from genlayer_py import create_client
    from genlayer_py.chains import testnet_bradbury

    pk = os.getenv("GENLAYER_ACCOUNT_PK", "")
    account = None
    if pk:
        from genlayer_py import create_account
        account = create_account(pk)

    client = create_client(chain=testnet_bradbury, account=account)

    try:
        block = client.get_block_number()
        print(f"Block number: {block}")
    except Exception as e:
        print(f"Could not get block number: {e}")

    if account:
        try:
            balance = client.get_balance(account.address)
            print(f"Account {account.address} balance: {balance}")
        except Exception as e:
            print(f"Could not read balance: {e}")


if __name__ == "__main__":
    inspect_bradbury()
