# Production Phase 2: Supabase/Postgres + Storage Migration

This phase moves Jarvis away from file-only state without breaking the working local demo.

## What is live now

- `client_store.py` handles clients + brand profiles.
- `draft_store.py` handles creative drafts + saved captions.
- `approval_store.py` handles pending approvals.
- `schedule_store.py` handles schedule jobs.
- `publish_run_store.py` handles publish history.
- `asset_store.py` handles media assets for either local files or Supabase Storage.

Structured state is now fully backend-aware. The only remaining operational cutover step is making sure your Supabase Storage bucket has the right policies so asset uploads can succeed.

## Supabase setup

1. Create a Supabase project.
2. Open the SQL editor.
3. Run `infra/supabase/schema.sql`
4. Create a storage bucket named `client-assets`
5. Make sure the storage policy section from `infra/supabase/schema.sql` is also applied. That file now includes:
   - bucket creation for `client-assets`
   - service-role policies on `storage.objects`
   These are required for Jarvis to upload media into Supabase Storage.
6. Add these env vars:

```env
JARVIS_DATA_BACKEND=supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_ASSET_BUCKET=client-assets
```

7. Install dependencies:

```bash
./venv/bin/pip install -r requirements.txt
```

8. Migrate the current JSON demo state into Supabase:

```bash
./venv/bin/python scripts/migrate_json_to_supabase.py
```

Use `--dry-run` first if you only want a source-state summary.

## What changes when `JARVIS_DATA_BACKEND=supabase`

- `/api/save-client-profile`
- `/api/client/{client_id}`
- `/api/client/{client_id}` update/delete
- `/api/clients`
- dashboard summary client discovery
- creative draft CRUD + caption storage
- schedule CRUD + delivery tracking
- approval queue storage
- caption agent brand-profile loading
- publish agent client credential loading
- orchestrator client/profile resolution

These paths will read/write core structured state from Supabase instead of:
- `clients/*.json`
- `brands/*.json`
- `assets/<client>/queue.json`
- `schedule.json`
- `pending_approvals.json`
- `publish_runs.json`

## What remains after the cutover

- log/event analytics tables if you want deeper production observability
- optional cleanup of legacy local `assets/` files once you fully trust Supabase Storage
- future draft identity migration from names to stable `draft_id`

## Migration order

1. Clients + brand profiles
2. Creative drafts
3. Schedule + approvals
4. Publish runs
5. Storage bucket migration

That order preserves the current live product while steadily removing JSON dependence.
