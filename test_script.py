import sys
import os
import json

from draft_store import get_draft_store
from asset_store import get_asset_store

print("Backend for drafts:", get_draft_store().backend_name)
print("Backend for assets:", get_asset_store().backend_name)

clients = ["Iron District gym", "Forge House Fitness Kuwait", "Burger mania"]

for c in clients:
    drafts = get_draft_store().list_drafts(c)
    assets = get_asset_store().list_assets(c)
    
    print(f"\n[{c}]")
    print("Drafts:", list(drafts.get('bundles', {}).keys()))
    print("Assets:", [a.get('filename') for a in assets])
