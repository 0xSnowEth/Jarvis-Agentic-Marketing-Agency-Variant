#!/usr/bin/env python3
"""Quick audit to check client data isolation."""
import json
import sys
sys.path.insert(0, "/home/snowaflic/agents")

from client_store import get_client_store
from draft_store import list_client_drafts
from asset_store import list_client_assets

store = get_client_store()
ids = store.list_client_ids()
print("=== CLIENTS ===")
print(json.dumps(ids, indent=2))

print("\n=== DRAFTS PER CLIENT ===")
for cid in ids:
    drafts = list_client_drafts(cid)
    bundles = drafts.get("bundles", {})
    print(f"  {cid}: {len(bundles)} drafts -> {list(bundles.keys())}")
    for name, payload in bundles.items():
        items = (payload or {}).get("items", [])
        filenames = [str(item.get("filename", "")) for item in items]
        draft_id = (payload or {}).get("draft_id", "??")
        print(f"    [{name}] draft_id={draft_id} files={filenames}")

print("\n=== ASSETS PER CLIENT ===")
for cid in ids:
    assets = list_client_assets(cid)
    fnames = [a.get("filename") for a in assets]
    print(f"  {cid}: {len(assets)} assets -> {fnames}")
