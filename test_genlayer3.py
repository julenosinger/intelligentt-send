import genlayer_py
import os
base = os.path.dirname(genlayer_py.__file__)
print("Base:", base)
for f in os.listdir(base):
    print(f)