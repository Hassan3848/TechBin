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
  org_id text not null,
  author_id uuid not null references auth.users(id) on delete cascade,
  author_email text not null,
  title text not null,
  body text not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz
);

alter table public.admin_messages enable row level security;
alter table public.org_announcements enable row level security;

create policy "profiles admin super contact read"
on public.profiles for select
to authenticated
using (
  public.current_is_admin()
  and super_admin = true
  and disabled = false
);

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
    and org_id = (select org_id from public.current_profile())
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
    public.current_is_super_admin()
    or org_id = (select org_id from public.current_profile())
  )
);

create policy "org announcements admin update"
on public.org_announcements for update
to authenticated
using (
  public.current_is_super_admin()
  or (
    public.current_is_admin()
    and org_id = (select org_id from public.current_profile())
  )
)
with check (
  public.current_is_super_admin()
  or (
    public.current_is_admin()
    and org_id = (select org_id from public.current_profile())
  )
);

create index if not exists admin_messages_sender_created_idx on public.admin_messages(sender_id, created_at desc);
create index if not exists admin_messages_recipient_created_idx on public.admin_messages(recipient_id, created_at desc);
create index if not exists org_announcements_org_created_idx on public.org_announcements(org_id, created_at desc);

alter publication supabase_realtime add table public.admin_messages;
alter publication supabase_realtime add table public.org_announcements;
