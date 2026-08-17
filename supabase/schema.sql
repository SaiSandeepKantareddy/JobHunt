-- Personal Job Radar synced tracker.
-- Run this in the Supabase SQL Editor after creating a free project.

create table if not exists public.job_tracker (
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id text not null,
  saved boolean not null default false,
  applied boolean not null default false,
  hidden boolean not null default false,
  notes text not null default '',
  stage text not null default 'open',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, job_id),
  constraint job_tracker_stage_check check (stage in ('open', 'saved', 'applied', 'interview', 'rejected', 'offer', 'hidden'))
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists job_tracker_set_updated_at on public.job_tracker;
create trigger job_tracker_set_updated_at
before update on public.job_tracker
for each row
execute function public.set_updated_at();

alter table public.job_tracker enable row level security;

drop policy if exists "Users can read their own job tracker rows." on public.job_tracker;
create policy "Users can read their own job tracker rows."
on public.job_tracker
for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert their own job tracker rows." on public.job_tracker;
create policy "Users can insert their own job tracker rows."
on public.job_tracker
for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update their own job tracker rows." on public.job_tracker;
create policy "Users can update their own job tracker rows."
on public.job_tracker
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can delete their own job tracker rows." on public.job_tracker;
create policy "Users can delete their own job tracker rows."
on public.job_tracker
for delete
to authenticated
using ((select auth.uid()) = user_id);

grant select, insert, update, delete on public.job_tracker to authenticated;

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'job_tracker'
  ) then
    alter publication supabase_realtime add table public.job_tracker;
  end if;
end;
$$;
