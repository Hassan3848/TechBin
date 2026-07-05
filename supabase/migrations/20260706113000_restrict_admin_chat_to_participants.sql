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
