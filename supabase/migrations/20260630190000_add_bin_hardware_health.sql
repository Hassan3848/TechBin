create table if not exists public.bin_hardware_health (
  bin_id text primary key references public.bins(id) on delete cascade,
  org_id text not null,
  bin_code text not null,
  hardware_health jsonb not null,
  overall_status text not null default 'unknown' check (overall_status in ('healthy', 'warning', 'critical', 'unknown')),
  received_at timestamptz not null default now(),
  device_last_checked_at timestamptz,
  device_last_success_at timestamptz,
  last_seen timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.bin_hardware_health enable row level security;

create policy "bin hardware health scoped read"
on public.bin_hardware_health for select
to authenticated
using (
  public.current_is_super_admin()
  or org_id = (select org_id from public.current_profile())
);

create index if not exists bin_hardware_health_org_updated_idx
on public.bin_hardware_health(org_id, updated_at desc);

alter publication supabase_realtime add table public.bin_hardware_health;
