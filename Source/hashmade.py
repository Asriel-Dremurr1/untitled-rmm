import os, hashlib

key = os.urandom(32)
key_hex = key.hex()
key_hash = hashlib.sha256(key).hexdigest()

print("Secret key (server):", key_hex)
print("SHA256 hash (agent.conf):", key_hash)
input()