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

alter table public.admin_conversations enable row level security;
alter table public.admin_conversation_messages enable row level security;

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

create index if not exists admin_conversations_org_admin_updated_idx on public.admin_conversations(org_admin_id, updated_at desc);
create index if not exists admin_conversations_super_admin_updated_idx on public.admin_conversations(super_admin_id, updated_at desc);
create index if not exists admin_conversation_messages_conversation_created_idx on public.admin_conversation_messages(conversation_id, created_at asc);

alter publication supabase_realtime add table public.admin_conversations;
alter publication supabase_realtime add table public.admin_conversation_messages;
