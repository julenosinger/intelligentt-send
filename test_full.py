import subprocess, time, os, requests

os.chdir("C:\\Users\\Juleno\\intelligent send")

# Start server
proc = subprocess.Popen(
    ["python", "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
time.sleep(3)

try:
    # Test chains
    r = requests.get("http://127.0.0.1:8000/v1/chains", timeout=5)
    print(f"=== /v1/chains ===")
    print(f"Status: {r.status_code}, Chains: {len(r.json())}")
    for c in r.json()[:3]:
        print(f"  - {c['name']} (chainId: {c['chain_id']})")
    
    # Test balances
    r2 = requests.get("http://127.0.0.1:8000/v1/wallet/0x742d35Cc6634C0532925a3b8D4C9B3a7e1f2345/balances?chainId=5042002", timeout=5)
    print(f"\n=== /v1/wallet/balances ===")
    print(f"Status: {r2.status_code}")
    print(r2.json())
    
    # Test validate address
    r3 = requests.post("http://127.0.0.1:8000/v1/address/validate", json={"address": "vitalik.eth", "chain_id": 11155111}, timeout=5)
    print(f"\n=== /v1/address/validate ===")
    print(f"Status: {r3.status_code}")
    print(r3.json())
    
    # Test gas estimate
    r4 = requests.post("http://127.0.0.1:8000/v1/gas/estimate", json={"chain_id": 5042002, "token": "ARC", "amount": "100", "speed": "standard"}, timeout=5)
    print(f"\n=== /v1/gas/estimate ===")
    print(f"Status: {r4.status_code}")
    print(r4.json())
    
    # Test AI analyze
    r5 = requests.post("http://127.0.0.1:8000/v1/ai/analyze", json={"chainId": 5042002, "to": "0x742d35Cc6634C0532925a3b8D4C9B3a7e1f2345", "amount": "100", "token": "USDC"}, timeout=5)
    print(f"\n=== /v1/ai/analyze ===")
    print(f"Status: {r5.status_code}")
    data = r5.json()
    print(f"  risk: {data['risk']}, cls: {data['cls']}, msg: {data['msg'][:60]}...")
    print(f"  checks: {len(data['checks'])}")
    
    # Test smart-transfer simulate
    r6 = requests.post("http://127.0.0.1:8000/v1/smart-transfer/simulate", json={
        "from_address": "0x742d35Cc6634C0532925a3b8D4C9B3a7e1f2345",
        "to_address": "0x1dE27a21",
        "amount": "100",
        "token": "USDC",
        "oracle_condition": "ETH price above $4000"
    }, timeout=5)
    print(f"\n=== /v1/smart-transfer/simulate ===")
    print(f"Status: {r6.status_code}")
    print(r6.json())
    
finally:
    proc.terminate()
    proc.wait()
    print("\nDone - server stopped")