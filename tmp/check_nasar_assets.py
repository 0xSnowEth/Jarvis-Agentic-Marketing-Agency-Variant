import sys
import os
import json

from asset_store import get_asset_store

store = get_asset_store()
assets = store.list_assets("Nasar_gym")

print("Nasar_gym Assets:")
for a in assets:
    print(a.get("filename"), json.dumps(a.get("metadata")))
