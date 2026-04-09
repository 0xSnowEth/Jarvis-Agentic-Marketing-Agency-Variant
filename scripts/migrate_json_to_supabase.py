import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from approval_store import JsonApprovalStore, SupabaseApprovalStore
from asset_store import JsonAssetStore, SupabaseAssetStore
from client_store import JsonClientStore, SupabaseClientStore
from draft_store import JsonDraftStore, SupabaseDraftStore
from schedule_store import JsonScheduleStore, SupabaseScheduleStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Jarvis JSON state into Supabase.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect source JSON state without writing to Supabase.")
    args = parser.parse_args()

    source_clients = JsonClientStore(ROOT)
    source_drafts = JsonDraftStore()
    source_schedule = JsonScheduleStore()
    source_approvals = JsonApprovalStore()
    source_assets = JsonAssetStore()

    client_ids = source_clients.list_client_ids()
    schedule_jobs = source_schedule.list_jobs()
    approvals = source_approvals.list_approvals()

    print("JSON source snapshot:")
    print(f"- clients: {len(client_ids)}")
    print(f"- schedule jobs: {len(schedule_jobs)}")
    print(f"- pending approvals: {len(approvals)}")
    for client_id in client_ids:
        draft_count = len(source_drafts.list_drafts(client_id).get("bundles", {}))
        asset_count = len(source_assets.list_assets(client_id))
        print(f"  - {client_id}: {draft_count} drafts | {asset_count} assets")

    if args.dry_run:
        print("\nDry-run only. No Supabase writes were performed.")
        return 0

    target_clients = SupabaseClientStore()
    target_drafts = SupabaseDraftStore()
    target_schedule = SupabaseScheduleStore()
    target_approvals = SupabaseApprovalStore()
    target_assets = SupabaseAssetStore()

    for client_id in client_ids:
        client_payload = source_clients.get_client(client_id) or {}
        brand_payload = source_clients.get_brand_profile(client_id) or {}
        target_clients.save_client(client_id, client_payload)
        target_clients.save_brand_profile(client_id, brand_payload)

        draft_map = source_drafts.list_drafts(client_id).get("bundles", {})
        for draft_name, payload in draft_map.items():
            target_drafts.save_draft(client_id, draft_name, payload)

        for asset in source_assets.list_assets(client_id):
            filename = str(asset.get("filename") or "").strip()
            content = source_assets.get_asset_content(client_id, filename)
            if not filename or not content:
                continue
            target_assets.save_asset(client_id, filename, content[0])

    target_schedule.replace_jobs(schedule_jobs)
    for approval in approvals:
        target_approvals.save_approval(approval)

    print("\nMigration complete.")
    print(f"- clients migrated: {len(client_ids)}")
    print(f"- schedule jobs migrated: {len(schedule_jobs)}")
    print(f"- pending approvals migrated: {len(approvals)}")
    print("- active asset files migrated to Supabase Storage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
