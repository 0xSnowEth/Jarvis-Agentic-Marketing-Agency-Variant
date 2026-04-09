import sys
import os
import json

from webhook_server import app
from fastapi.testclient import TestClient

client = TestClient(app)

res = client.get("/api/clients")
print("Clients:", res.json())

clients = res.json()["clients"]
for c in clients:
    vault_res = client.get(f"/api/vault/{c}")
    print(f"Vault {c}:", json.dumps(vault_res.json(), indent=2))
