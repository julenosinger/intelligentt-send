"""Utility script to inspect GenLayer Bradbury network state."""
import asyncio
import os

async def inspect_bradbury():
    """Inspect the Bradbury GenLayer network."""
    from genlayer import create_client

    rpc = os.getenv("GENLAYER_RPC", "https://rpc-bradbury.genlayer.com")
    network = os.getenv("GENLAYER_NETWORK", "bradbury")
    pk = os.getenv("GENLAYER_ACCOUNT_PK", "")

    if not pk:
        print("Set GENLAYER_ACCOUNT_PK to use this script")
        return

    client = create_client(rpc_url=rpc, network=network, account_pk=pk)

    # Check account balance
    try:
        balance = await client.read_contract(
            address="0x0000000000000000000000000000000000000000",
            function_name="getBalance",
            args=[],
        )
        print(f"Account balance: {balance}")
    except Exception as e:
        print(f"Could not read balance: {e}")

    # Check network info
    try:
        block = await client.read_contract(
            address="0x0000000000000000000000000000000000000000",
            function_name="getCurrentBlock",
            args=[],
        )
        print(f"Current block: {block}")
    except Exception as e:
        print(f"Could not get block: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_bradbury())