# Personal Dashboard

A set of small, self-contained HTML apps that share a top bar.

## Deploy your own copy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FRowanThistlebrooke%2FYTdashh1)

One click → Vercel signs you in, copies the repo to your GitHub, and deploys it. ~30 seconds to a live URL.

## How to use

Open any `.html` file directly in your browser — no build step, no install.

| File | What it is |
|---|---|
| [index.html](index.html) | Bento grid hub — the home page, links out to every tracker |
| [main.html](main.html) | Goals tracker (Day Ring, Goal Ticker, To Do list) |
| [health.html](health.html) | Supplement / daily stack tracker |
| [po-water.html](po-water.html) | Water intake tracker |
| [finance.html](finance.html) | Finances |
| [gym.html](gym.html) | Progressive overload gym tracker |
| [topbar.js](topbar.js) | Shared top bar — auto-injected into pages that `<script src="topbar.js">` |

Each app stores its own state in browser `localStorage`. No accounts, no server.

## Cloud sync setup (optional)

To sync data (and gym progress photos) across devices, create a free [Supabase](https://supabase.com) project, paste its Project URL + publishable key into `topbar.js`, `sync.js`, and `gym.html`, then run this in the Supabase SQL Editor to set up Storage for progress photos:

```sql
insert into storage.buckets (id, name, public)
values ('progress-photos', 'progress-photos', true)
on conflict (id) do update set public = true;

drop policy if exists "anon upload progress-photos" on storage.objects;
drop policy if exists "anon read progress-photos"   on storage.objects;
drop policy if exists "anon delete progress-photos" on storage.objects;

create policy "anon upload progress-photos"
  on storage.objects for insert with check (bucket_id = 'progress-photos');

create policy "anon read progress-photos"
  on storage.objects for select using (bucket_id = 'progress-photos');

create policy "anon delete progress-photos"
  on storage.objects for delete using (bucket_id = 'progress-photos');
```

You'll also need a `public.app_state` table (key text primary key, data jsonb, updated_at timestamptz) with RLS policies allowing anon select/insert/update — this is what `topbar.js`, `sync.js`, and `gym.html` read/write for everything except photos.

## Building from scratch

[BUILD_DASHBOARD.md](BUILD_DASHBOARD.md) is the prompt I gave Claude to generate `main.html` (the goals tracker) — paste it into Claude if you want to rebuild that page yourself.
