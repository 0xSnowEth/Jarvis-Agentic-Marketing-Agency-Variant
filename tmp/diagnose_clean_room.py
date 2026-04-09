import os
import sys

from asset_store import get_asset_store
from draft_store import get_draft_store
from client_store import get_client_store

print("Starting clean room diagnostic...")

client_store = get_client_store()
clients = client_store.list_clients()

for c in clients:
    cid = c['client_id']
    assets = get_asset_store().list_assets(cid)
    drafts = get_draft_store().list_drafts(cid).get("bundles", {})
    
    print(f"\n--- {cid} ---")
    print(f"Total Assets: {len(assets)}")
    if len(assets) > 0:
        for a in assets:
            print(f" - {a.get('filename')} (bucket={a.get('storage_bucket')}, path={a.get('storage_path')})")
    
    print(f"Total Drafts: {len(drafts)}")
    if len(drafts) > 0:
        for name, payload in drafts.items():
            print(f" - [{name}] Files: {[x.get('filename') for x in payload.get('items', [])]}")
