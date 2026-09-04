import subprocess
import time
import requests
import os

os.chdir("C:\\Users\\Juleno\\intelligent send")

# Start the server
proc = subprocess.Popen(
    ["python", "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Wait for startup
time.sleep(3)

try:
    # Test chains endpoint
    r = requests.get("http://127.0.0.1:8000/v1/chains", timeout=5)
    print("=== /v1/chains ===")
    print(f"Status: {r.status_code}")
    chains = r.json()
    print(f"Number of chains: {len(chains)}")
    for c in chains:
        print(f"  - {c['name']} (chainId: {c['chain_id']})")
    
    # Test wallet balances with chainId query param
    r2 = requests.get("http://127.0.0.1:8000/v1/wallet/0x742d35Cc6634C0532925a3b8D4C9B3a7e1f2345/balances?chainId=5042002", timeout=5)
    print("\n=== /v1/wallet/:address/balances?chainId=5042002 ===")
    print(f"Status: {r2.status_code}")
    print(r2.json())
    
    # Test address validate
    r3 = requests.post("http://127.0.0.1:8000/v1/address/validate", json={"address": "vitalik.eth", "chain_id": 11155111}, timeout=5)
    print("\n=== /v1/address/validate ===")
    print(f"Status: {r3.status_code}")
    print(r3.json())
    
    # Test gas estimate
    r4 = requests.post("http://127.0.0.1:8000/v1/gas/estimate", json={"chain_id": 5042002, "token": "ARC", "amount": "100", "speed": "standard"}, timeout=5)
    print("\n=== /v1/gas/estimate ===")
    print(f"Status: {r4.status_code}")
    print(r4.json())
    
    # Test AI analyze
    r5 = requests.post("http://127.0.0.1:8000/v1/ai/analyze", json={"chainId": 5042002, "to": "0x742d35Cc6634C0532925a3b8D4C9B3a7e1f2345", "amount": "100", "token": "USDC"}, timeout=5)
    print("\n=== /v1/ai/analyze ===")
    print(f"Status: {r5.status_code}")
    result = r5.json()
    print(f"risk: {result['risk']}, cls: {result['cls']}, msg: {result['msg'][:50]}...")
    print(f"checks: {len(result['checks'])} checks")
    
    # Test smart-transfer simulate
    r6 = requests.post("http://127.0.0.1:8000/v1/smart-transfer/simulate", json={
        "from_address": "0x742d35Cc6634C0532925a3b8D4C9B3a7e1f2345",
        "to_address": "0x1dE27a21",
        "amount": "100",
        "token": "USDC",
        "oracle_condition": "ETH price above $4000"
    }, timeout=5)
    print("\n=== /v1/smart-transfer/simulate ===")
    print(f"Status: {r6.status_code}")
    print(r6.json())
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    proc.terminate()
    proc.wait()
    print("\nDone.")