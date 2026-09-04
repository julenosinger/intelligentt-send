import genlayer_py
import os
base = os.path.dirname(genlayer_py.__file__)
client_dir = os.path.join(base, 'client')
print("Client dir:", client_dir)
if os.path.isdir(client_dir):
    for f in os.listdir(client_dir):
        print(f)