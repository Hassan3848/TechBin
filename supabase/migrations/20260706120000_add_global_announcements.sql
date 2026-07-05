alter table public.org_announcements
add column if not exists audience text not null default 'org';

alter table public.org_announcements
alter column org_id drop not null;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'org_announcements_audience_check'
      and conrelid = 'public.org_announcements'::regclass
  ) then
    alter table public.org_announcements
    add constraint org_announcements_audience_check
    check (audience in ('org', 'all'));
  end if;
end $$;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'org_announcements_audience_org_check'
      and conrelid = 'public.org_announcements'::regclass
  ) then
    alter table public.org_announcements
    add constraint org_announcements_audience_org_check
    check (
      (audience = 'org' and org_id is not null)
      or (audience = 'all' and org_id is null)
    );
  end if;
end $$;

drop policy if exists "org announcements scoped read" on public.org_announcements;
drop policy if exists "org announcements admin insert" on public.org_announcements;
drop policy if exists "org announcements admin update" on public.org_announcements;

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

create index if not exists org_announcements_audience_created_idx
on public.org_announcements(audience, created_at desc);
