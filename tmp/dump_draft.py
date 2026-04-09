import sys
import json
from draft_store import get_draft_store
from asset_store import get_asset_store

cid = 'Nasar_gym'
drafts = get_draft_store().list_drafts(cid).get('bundles', {})
target = None
for k, v in drafts.items():
    if 'yum' in k.lower() or 'burger' in k.lower():
        target = v
        name = k
        break

print(f"DRAFT {name}:", json.dumps(target, indent=2))
if target:
    for item in target.get('items', []):
        fname = item.get('filename')
        print('FILE:', fname)
        asset = get_asset_store()._list_rows(cid, filename=fname)
        if asset:
            print('METADATA:', json.dumps(asset[0].get('metadata'), indent=2))
