create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  display_name text,
  role text not null check (role in ('Admin', 'Viewer')),
  org_id text not null,
  super_admin boolean not null default false,
  disabled boolean not null default false,
  created_at timestamptz not null default now(),
  created_by text,
  updated_at timestamptz,
  updated_by text
);

create table if not exists public.user_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  org_id text not null,
  refresh_rate text not null default '10',
  session_timeout text not null default '30',
  theme text not null default 'light' check (theme in ('light', 'dark')),
  notifications boolean not null default true,
  created_at timestamptz not null default now(),
  created_by text,
  updated_at timestamptz,
  updated_by text
);

create table if not exists public.bins (
  id text primary key,
  org_id text not null,
  bin_code text not null,
  location text,
  status text not null default 'Active' check (status in ('Active', 'Maintenance', 'Inactive')),
  capacity_liters numeric,
  created_at timestamptz not null default now(),
  created_by text,
  updated_at timestamptz,
  updated_by text,
  unique (org_id, bin_code)
);

create table if not exists public.bin_states (
  bin_id text primary key references public.bins(id) on delete cascade,
  org_id text not null,
  bin_code text not null,
  status jsonb not null default '{}'::jsonb,
  sensors jsonb not null default '{}'::jsonb,
  statistics jsonb not null default '{}'::jsonb,
  faults jsonb not null default '{}'::jsonb,
  latest_event jsonb,
  last_seen timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bin_events (
  id uuid primary key default gen_random_uuid(),
  event_id text,
  bin_id text not null references public.bins(id) on delete cascade,
  org_id text not null,
  bin_code text not null,
  timestamp timestamptz not null default now(),
  label text,
  category text,
  recyclable boolean,
  disposed_side text,
  expected_side text,
  correct boolean,
  confidence numeric,
  image_url text,
  payload jsonb not null default '{}'::jsonb
);

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

create table if not exists public.pi_devices (
  id uuid primary key default gen_random_uuid(),
  bin_id text not null references public.bins(id) on delete cascade,
  org_id text not null,
  bin_code text not null,
  device_name text not null,
  token_hash text not null,
  active boolean not null default true,
  last_seen timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.admin_messages (
  id uuid primary key default gen_random_uuid(),
  sender_id uuid not null references auth.users(id) on delete cascade,
  sender_email text not null,
  sender_org_id text not null,
  recipient_id uuid not null references auth.users(id) on delete cascade,
  recipient_email text not null,
  recipient_org_id text not null,
  subject text not null,
  body text not null,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.org_announcements (
  id uuid primary key default gen_random_uuid(),
  org_id text,
  audience text not null default 'org' check (audience in ('org', 'all')),
  author_id uuid not null references auth.users(id) on delete cascade,
  author_email text not null,
  title text not null,
  body text not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz,
  constraint org_announcements_audience_org_check check (
    (audience = 'org' and org_id is not null)
    or (audience = 'all' and org_id is null)
  )
);

create table if not exists public.admin_conversations (
  id uuid primary key default gen_random_uuid(),
  org_admin_id uuid not null references auth.users(id) on delete cascade,
  org_admin_email text not null,
  org_id text not null,
  super_admin_id uuid not null references auth.users(id) on delete cascade,
  super_admin_email text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (org_admin_id, super_admin_id)
);

create table if not exists public.admin_conversation_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.admin_conversations(id) on delete cascade,
  sender_id uuid not null references auth.users(id) on delete cascade,
  sender_email text not null,
  body text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.admin_chat_conversations (
  id uuid primary key default gen_random_uuid(),
  org_id text not null,
  participant_a_id uuid not null references auth.users(id) on delete cascade,
  participant_a_email text not null,
  participant_a_org_id text not null,
  participant_a_super_admin boolean not null default false,
  participant_b_id uuid not null references auth.users(id) on delete cascade,
  participant_b_email text not null,
  participant_b_org_id text not null,
  participant_b_super_admin boolean not null default false,
  created_by uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (participant_a_id <> participant_b_id),
  unique (participant_a_id, participant_b_id)
);

create table if not exists public.admin_chat_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.admin_chat_conversations(id) on delete cascade,
  sender_id uuid not null references auth.users(id) on delete cascade,
  sender_email text not null,
  body text not null,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.user_settings enable row level security;
alter table public.bins enable row level security;
alter table public.bin_states enable row level security;
alter table public.bin_events enable row level security;
alter table public.bin_hardware_health enable row level security;
alter table public.pi_devices enable row level security;
alter table public.admin_messages enable row level security;
alter table public.org_announcements enable row level security;
alter table public.admin_conversations enable row level security;
alter table public.admin_conversation_messages enable row level security;
alter table public.admin_chat_conversations enable row level security;
alter table public.admin_chat_messages enable row level security;

create or replace function public.current_profile()
returns public.profiles
language sql
stable
security definer
set search_path = public
as $$
  select * from public.profiles where id = auth.uid() and disabled = false limit 1
$$;

create or replace function public.current_is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists(select 1 from public.profiles where id = auth.uid() and disabled = false and role = 'Admin')
$$;

create or replace function public.current_is_super_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists(select 1 from public.profiles where id = auth.uid() and disabled = false and super_admin = true)
$$;

create or replace function public.current_can_access_admin_conversation(conversation public.admin_conversations)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select
    public.current_is_super_admin()
    or (
      public.current_is_admin()
      and conversation.org_admin_id = auth.uid()
    )
$$;

create or replace function public.current_can_access_admin_chat(conversation public.admin_chat_conversations)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select
    public.current_is_admin()
    and auth.uid() in (conversation.participant_a_id, conversation.participant_b_id)
$$;

create policy "profiles admin scoped read"
on public.profiles for select
to authenticated
using (
  public.current_is_super_admin()
  or (
    public.current_is_admin()
    and org_id = (select org_id from public.current_profile())
    and super_admin = false
  )
  or id = auth.uid()
);

create policy "profiles admin super contact read"
on public.profiles for select
to authenticated
using (
  public.current_is_admin()
  and super_admin = true
  and disabled = false
);

create policy "settings owner read"
on public.user_settings for select
to authenticated
using (user_id = auth.uid());

create policy "settings owner upsert"
on public.user_settings for insert
to authenticated
with check (user_id = auth.uid());

create policy "settings owner update"
on public.user_settings for update
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

create policy "bins scoped read"
on public.bins for select
to authenticated
using (
  public.current_is_super_admin()
  or org_id = (select org_id from public.current_profile())
);

create policy "bins super admin create"
on public.bins for insert
to authenticated
with check (public.current_is_super_admin());

create policy "bins admin scoped update"
on public.bins for update
to authenticated
using (
  public.current_is_super_admin()
  or (public.current_is_admin() and org_id = (select org_id from public.current_profile()))
)
with check (
  public.current_is_super_admin()
  or (public.current_is_admin() and org_id = (select org_id from public.current_profile()))
);

create policy "bins super admin delete"
on public.bins for delete
to authenticated
using (public.current_is_super_admin());

create policy "bin states scoped read"
on public.bin_states for select
to authenticated
using (
  public.current_is_super_admin()
  or org_id = (select org_id from public.current_profile())
);

create policy "bin events scoped read"
on public.bin_events for select
to authenticated
using (
  public.current_is_super_admin()
  or org_id = (select org_id from public.current_profile())
);

create policy "bin hardware health scoped read"
on public.bin_hardware_health for select
to authenticated
using (
  public.current_is_super_admin()
  or org_id = (select org_id from public.current_profile())
);

create policy "pi devices super admin read"
on public.pi_devices for select
to authenticated
using (public.current_is_super_admin());

create policy "admin messages scoped read"
on public.admin_messages for select
to authenticated
using (
  public.current_is_super_admin()
  or (
    public.current_is_admin()
    and (sender_id = auth.uid() or recipient_id = auth.uid())
  )
);

create policy "admin messages scoped insert"
on public.admin_messages for insert
to authenticated
with check (
  public.current_is_admin()
  and sender_id = auth.uid()
  and sender_email = (select email from public.current_profile())
  and sender_org_id = (select org_id from public.current_profile())
  and (
    (
      public.current_is_super_admin()
      and exists (
        select 1
        from public.profiles recipient
        where recipient.id = recipient_id
          and recipient.role = 'Admin'
          and recipient.disabled = false
          and recipient_email = recipient.email
          and recipient_org_id = recipient.org_id
      )
    )
    or (
      not public.current_is_super_admin()
      and exists (
        select 1
        from public.profiles recipient
        where recipient.id = recipient_id
          and recipient.super_admin = true
          and recipient.disabled = false
          and recipient_email = recipient.email
          and recipient_org_id = recipient.org_id
      )
    )
  )
);

create policy "org announcements scoped read"
on public.org_announcements for select
to authenticated
using (
  public.current_is_super_admin()
  or (
    active = true
    and (
      audience = 'all'
      or org_id = (select org_id from public.current_profile())
    )
  )
);

create policy "org announcements admin insert"
on public.org_announcements for insert
to authenticated
with check (
  public.current_is_admin()
  and author_id = auth.uid()
  and author_email = (select email from public.current_profile())
  and (
    (
      public.current_is_super_admin()
      and (
        (audience = 'all' and org_id is null)
        or (audience = 'org' and org_id is not null)
      )
    )
    or (
      not public.current_is_super_admin()
      and audience = 'org'
      and org_id = (select org_id from public.current_profile())
    )
  )
);

create policy "org announcements admin update"
on public.org_announcements for update
to authenticated
using (
  public.current_is_super_admin()
  or (
    public.current_is_admin()
    and audience = 'org'
    and org_id = (select org_id from public.current_profile())
  )
)
with check (
  public.current_is_super_admin()
  or (
    public.current_is_admin()
    and audience = 'org'
    and org_id = (select org_id from public.current_profile())
  )
);

create policy "admin conversations scoped read"
on public.admin_conversations for select
to authenticated
using (public.current_can_access_admin_conversation(admin_conversations));

create policy "admin conversations scoped insert"
on public.admin_conversations for insert
to authenticated
with check (
  public.current_is_admin()
  and (
    (
      public.current_is_super_admin()
      and super_admin_id = auth.uid()
      and super_admin_email = (select email from public.current_profile())
      and exists (
        select 1
        from public.profiles org_admin
        where org_admin.id = org_admin_id
          and org_admin.email = org_admin_email
          and org_admin.org_id = org_id
          and org_admin.role = 'Admin'
          and org_admin.super_admin = false
          and org_admin.disabled = false
      )
    )
    or (
      not public.current_is_super_admin()
      and org_admin_id = auth.uid()
      and org_admin_email = (select email from public.current_profile())
      and org_id = (select org_id from public.current_profile())
      and exists (
        select 1
        from public.profiles super_admin
        where super_admin.id = super_admin_id
          and super_admin.email = super_admin_email
          and super_admin.super_admin = true
          and super_admin.disabled = false
      )
    )
  )
);

create policy "admin conversation messages scoped read"
on public.admin_conversation_messages for select
to authenticated
using (
  exists (
    select 1
    from public.admin_conversations conversation
    where conversation.id = conversation_id
      and public.current_can_access_admin_conversation(conversation)
  )
);

create policy "admin conversation messages scoped insert"
on public.admin_conversation_messages for insert
to authenticated
with check (
  public.current_is_admin()
  and sender_id = auth.uid()
  and sender_email = (select email from public.current_profile())
  and exists (
    select 1
    from public.admin_conversations conversation
    where conversation.id = conversation_id
      and public.current_can_access_admin_conversation(conversation)
  )
);

create or replace function public.touch_admin_conversation_updated_at()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.admin_conversations
  set updated_at = new.created_at
  where id = new.conversation_id;
  return new;
end;
$$;

drop trigger if exists admin_conversation_messages_touch_conversation on public.admin_conversation_messages;
create trigger admin_conversation_messages_touch_conversation
after insert on public.admin_conversation_messages
for each row execute function public.touch_admin_conversation_updated_at();

create policy "admin chat conversations scoped read"
on public.admin_chat_conversations for select
to authenticated
using (public.current_can_access_admin_chat(admin_chat_conversations));

create policy "admin chat conversations scoped insert"
on public.admin_chat_conversations for insert
to authenticated
with check (
  public.current_is_admin()
  and created_by = auth.uid()
  and auth.uid() in (participant_a_id, participant_b_id)
  and exists (
    select 1
    from public.profiles participant_a
    where participant_a.id = participant_a_id
      and participant_a.email = participant_a_email
      and participant_a.org_id = participant_a_org_id
      and participant_a.super_admin = participant_a_super_admin
      and participant_a.role = 'Admin'
      and participant_a.disabled = false
  )
  and exists (
    select 1
    from public.profiles participant_b
    where participant_b.id = participant_b_id
      and participant_b.email = participant_b_email
      and participant_b.org_id = participant_b_org_id
      and participant_b.super_admin = participant_b_super_admin
      and participant_b.role = 'Admin'
      and participant_b.disabled = false
  )
  and (
    participant_a_super_admin = true
    or participant_b_super_admin = true
    or participant_a_org_id = participant_b_org_id
  )
  and (
    public.current_is_super_admin()
    or (
      participant_a_org_id = (select org_id from public.current_profile())
      and participant_b_org_id = (select org_id from public.current_profile())
      and participant_a_super_admin = false
      and participant_b_super_admin = false
    )
    or (
      (participant_a_super_admin = true or participant_b_super_admin = true)
      and (
        participant_a_org_id = (select org_id from public.current_profile())
        or participant_b_org_id = (select org_id from public.current_profile())
      )
    )
  )
);

create policy "admin chat messages scoped read"
on public.admin_chat_messages for select
to authenticated
using (
  exists (
    select 1
    from public.admin_chat_conversations conversation
    where conversation.id = conversation_id
      and public.current_can_access_admin_chat(conversation)
  )
);

create policy "admin chat messages scoped insert"
on public.admin_chat_messages for insert
to authenticated
with check (
  public.current_is_admin()
  and sender_id = auth.uid()
  and sender_email = (select email from public.current_profile())
  and exists (
    select 1
    from public.admin_chat_conversations conversation
    where conversation.id = conversation_id
      and public.current_can_access_admin_chat(conversation)
      and auth.uid() in (conversation.participant_a_id, conversation.participant_b_id)
  )
);

create or replace function public.touch_admin_chat_conversation_updated_at()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.admin_chat_conversations
  set updated_at = new.created_at
  where id = new.conversation_id;
  return new;
end;
$$;

drop trigger if exists admin_chat_messages_touch_conversation on public.admin_chat_messages;
create trigger admin_chat_messages_touch_conversation
after insert on public.admin_chat_messages
for each row execute function public.touch_admin_chat_conversation_updated_at();

create index if not exists profiles_org_created_idx on public.profiles(org_id, created_at desc);
create index if not exists bins_org_created_idx on public.bins(org_id, created_at desc);
create index if not exists bin_events_bin_timestamp_idx on public.bin_events(bin_id, timestamp desc);
create unique index if not exists bin_events_bin_event_id_unique on public.bin_events(bin_id, event_id);
create index if not exists bin_hardware_health_org_updated_idx on public.bin_hardware_health(org_id, updated_at desc);
create index if not exists admin_messages_sender_created_idx on public.admin_messages(sender_id, created_at desc);
create index if not exists admin_messages_recipient_created_idx on public.admin_messages(recipient_id, created_at desc);
create index if not exists org_announcements_org_created_idx on public.org_announcements(org_id, created_at desc);
create index if not exists org_announcements_audience_created_idx on public.org_announcements(audience, created_at desc);
create index if not exists admin_conversations_org_admin_updated_idx on public.admin_conversations(org_admin_id, updated_at desc);
create index if not exists admin_conversations_super_admin_updated_idx on public.admin_conversations(super_admin_id, updated_at desc);
create index if not exists admin_conversation_messages_conversation_created_idx on public.admin_conversation_messages(conversation_id, created_at asc);
create index if not exists admin_chat_conversations_participant_a_updated_idx on public.admin_chat_conversations(participant_a_id, updated_at desc);
create index if not exists admin_chat_conversations_participant_b_updated_idx on public.admin_chat_conversations(participant_b_id, updated_at desc);
create index if not exists admin_chat_conversations_org_updated_idx on public.admin_chat_conversations(org_id, updated_at desc);
create index if not exists admin_chat_messages_conversation_created_idx on public.admin_chat_messages(conversation_id, created_at asc);

alter publication supabase_realtime add table public.bins;
alter publication supabase_realtime add table public.bin_states;
alter publication supabase_realtime add table public.bin_events;
alter publication supabase_realtime add table public.bin_hardware_health;
alter publication supabase_realtime add table public.admin_messages;
alter publication supabase_realtime add table public.org_announcements;
alter publication supabase_realtime add table public.admin_conversations;
alter publication supabase_realtime add table public.admin_conversation_messages;
alter publication supabase_realtime add table public.admin_chat_conversations;
alter publication supabase_realtime add table public.admin_chat_messages;
