create extension if not exists pgcrypto;

insert into storage.buckets (id, name, public)
values ('client-assets', 'client-assets', true)
on conflict (id) do update set public = true;

create table if not exists clients (
  client_id text primary key,
  phone_number text,
  meta_access_token text,
  facebook_page_id text,
  instagram_account_id text,
  profile_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists client_brand_profiles (
  client_id text primary key references clients(client_id) on delete cascade,
  brand_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists assets (
  asset_id uuid primary key default gen_random_uuid(),
  client_id text not null references clients(client_id) on delete cascade,
  storage_bucket text not null default 'client-assets',
  storage_path text not null,
  original_filename text not null,
  media_kind text not null check (media_kind in ('image', 'video')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists creative_drafts (
  draft_id uuid primary key default gen_random_uuid(),
  client_id text not null references clients(client_id) on delete cascade,
  draft_name text not null,
  bundle_type text not null check (bundle_type in ('image_single', 'image_carousel', 'video')),
  items jsonb not null default '[]'::jsonb,
  caption_mode text not null default 'ai',
  caption_status text not null default 'empty',
  caption_text text not null default '',
  hashtags jsonb not null default '[]'::jsonb,
  seo_keyword_used text not null default '',
  topic_hint text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (client_id, draft_name)
);

create table if not exists schedule_jobs (
  job_id text primary key,
  client_id text not null references clients(client_id) on delete cascade,
  draft_id uuid references creative_drafts(draft_id) on delete set null,
  draft_name text,
  topic text,
  status text not null default 'approved',
  media_kind text,
  days jsonb not null default '[]'::jsonb,
  scheduled_date date,
  time_text text,
  images jsonb not null default '[]'::jsonb,
  videos jsonb not null default '[]'::jsonb,
  approval_id text,
  payload_json jsonb not null default '{}'::jsonb,
  delivered_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists approval_requests (
  approval_id text primary key,
  client_id text not null references clients(client_id) on delete cascade,
  job_id text,
  status text not null default 'pending_approval',
  payload_json jsonb not null default '{}'::jsonb,
  requested_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists publish_runs (
  run_id uuid primary key default gen_random_uuid(),
  client_id text not null references clients(client_id) on delete cascade,
  job_id text,
  draft_id uuid references creative_drafts(draft_id) on delete set null,
  topic text,
  status text not null,
  failure_step text,
  platform_results jsonb not null default '{}'::jsonb,
  raw_output text,
  created_at timestamptz not null default now()
);

create table if not exists auth_sessions (
  session_token text primary key,
  expires_at timestamptz not null,
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_seen_at timestamptz
);

create table if not exists orchestrator_runs (
  run_id text primary key,
  status text not null default 'queued',
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists reschedule_sessions (
  phone text primary key,
  payload_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists operator_audit_events (
  event_id uuid primary key default gen_random_uuid(),
  event_type text not null,
  actor text,
  request_id text,
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_assets_client_id on assets(client_id);
create unique index if not exists idx_assets_client_filename on assets(client_id, original_filename);
create index if not exists idx_drafts_client_id on creative_drafts(client_id);
create index if not exists idx_schedule_jobs_client_id on schedule_jobs(client_id);
create index if not exists idx_schedule_jobs_scheduled_date on schedule_jobs(scheduled_date);
create index if not exists idx_schedule_jobs_status on schedule_jobs(status);
create index if not exists idx_approval_requests_client_id on approval_requests(client_id);
create index if not exists idx_publish_runs_client_id on publish_runs(client_id);
create index if not exists idx_auth_sessions_expires_at on auth_sessions(expires_at);
create index if not exists idx_orchestrator_runs_status on orchestrator_runs(status);
create index if not exists idx_orchestrator_runs_updated_at on orchestrator_runs(updated_at);
create index if not exists idx_operator_audit_events_type on operator_audit_events(event_type);
create index if not exists idx_operator_audit_events_created_at on operator_audit_events(created_at);

drop policy if exists "jarvis_service_role_select_client_assets" on storage.objects;
create policy "jarvis_service_role_select_client_assets"
on storage.objects for select
to service_role
using (bucket_id = 'client-assets');

drop policy if exists "jarvis_service_role_insert_client_assets" on storage.objects;
create policy "jarvis_service_role_insert_client_assets"
on storage.objects for insert
to service_role
with check (bucket_id = 'client-assets');

drop policy if exists "jarvis_service_role_update_client_assets" on storage.objects;
create policy "jarvis_service_role_update_client_assets"
on storage.objects for update
to service_role
using (bucket_id = 'client-assets')
with check (bucket_id = 'client-assets');

drop policy if exists "jarvis_service_role_delete_client_assets" on storage.objects;
create policy "jarvis_service_role_delete_client_assets"
on storage.objects for delete
to service_role
using (bucket_id = 'client-assets');
