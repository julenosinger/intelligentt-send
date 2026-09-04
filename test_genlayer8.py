import genlayer_py.chains.testnet_bradbury as bradbury
print('Chain ID:', bradbury.id)
print('RPC default:', bradbury.rpc_urls['default']['http'][0])
print('Explorer:', bradbury.explorer)
print('Faucet:', bradbury.faucet)