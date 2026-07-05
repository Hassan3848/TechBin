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

alter table public.admin_chat_conversations enable row level security;
alter table public.admin_chat_messages enable row level security;

create or replace function public.current_can_access_admin_chat(conversation public.admin_chat_conversations)
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
      and auth.uid() in (conversation.participant_a_id, conversation.participant_b_id)
    )
$$;

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

create index if not exists admin_chat_conversations_participant_a_updated_idx
on public.admin_chat_conversations(participant_a_id, updated_at desc);

create index if not exists admin_chat_conversations_participant_b_updated_idx
on public.admin_chat_conversations(participant_b_id, updated_at desc);

create index if not exists admin_chat_conversations_org_updated_idx
on public.admin_chat_conversations(org_id, updated_at desc);

create index if not exists admin_chat_messages_conversation_created_idx
on public.admin_chat_messages(conversation_id, created_at asc);

alter publication supabase_realtime add table public.admin_chat_conversations;
alter publication supabase_realtime add table public.admin_chat_messages;
