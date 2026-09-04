import genlayer_py
import os
base = os.path.dirname(genlayer_py.__file__)
contracts_dir = os.path.join(base, 'contracts')
print("Contracts dir:", contracts_dir)
if os.path.isdir(contracts_dir):
    for f in os.listdir(contracts_dir):
        print(f)