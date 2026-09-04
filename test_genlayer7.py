import genlayer_py
import os
base = os.path.dirname(genlayer_py.__file__)
chain_mod = genlayer_py.chains.testnet_bradbury
print("Chain name:", chain_mod.name)
print("Chain id:", chain_mod.id)
print("RPC URLs:", chain_mod.rpc_urls)
print("Consensus main contract:", getattr(chain_mod, 'consensus_main_contract', 'N/A'))
print("Consensus data contract:", getattr(chain_mod, 'consensus_data_contract', 'N/A'))
print("Appeals contract:", getattr(chain_mod, 'appeals_contract', 'N/A'))
print("Fee manager contract:", getattr(chain_mod, 'fee_manager_contract', 'N/A'))
print("Default number of validators:", getattr(chain_mod, 'default_number_of_initial_validators', 'N/A'))
print("Default consensus max rotations:", getattr(chain_mod, 'default_consensus_max_rotations', 'N/A'))