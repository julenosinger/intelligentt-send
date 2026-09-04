import genlayer_py
import os
base = os.path.dirname(genlayer_py.__file__)
chains_dir = os.path.join(base, 'chains')
print("Chains dir:", chains_dir)
if os.path.isdir(chains_dir):
    for f in os.listdir(chains_dir):
        print(f)