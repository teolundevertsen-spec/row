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
| [caffeine.html](caffeine.html) | Caffeine tracker — searchable drink database, peak/comedown/clearance estimates, daily limit bar |
| [po-water.html](po-water.html) | Water intake tracker |
| [finance.html](finance.html) | Finances |
| [gym.html](gym.html) | Progressive overload gym tracker |
| [topbar.js](topbar.js) | Shared top bar — auto-injected into pages that `<script src="topbar.js">` |
| [section-template.html](section-template.html) | Starter template for a new page/section — same design system + cloud sync, ready to copy |

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

## Garmin sync setup (optional)

[api/garmin-sync.py](api/garmin-sync.py) is a Vercel Python serverless function that logs into Garmin Connect once a day (via [vercel.json](vercel.json)'s cron config) and writes resting heart rate, body battery and sleep into the `garmin` row of the same `app_state` table — [health.html](health.html)'s "Vitals" card reads it from there.

It uses the unofficial [`garminconnect`](https://pypi.org/project/garminconnect/) library (there's no realistic path to Garmin's official Developer API for a personal project — that requires business approval). To turn it on:

1. In your Vercel project → **Settings → Environment Variables**, add:
   - `GARMIN_EMAIL` — your Garmin Connect login email
   - `GARMIN_PASSWORD` — your Garmin Connect login password
   - `CRON_SECRET` — any random string (Vercel automatically sends this back as a bearer token when it triggers the cron job, so the public function URL can't be used by randoms to trigger a Garmin login)
2. Redeploy. The cron in `vercel.json` runs daily at 09:00 UTC — edit the schedule string if you want a different time.
3. To test it immediately rather than waiting for the cron, visit `https://<your-app>.vercel.app/api/garmin-sync` with an `Authorization: Bearer <your CRON_SECRET>` header (e.g. `curl -H "Authorization: Bearer <secret>" https://.../api/garmin-sync`).

**Note on credentials:** never put your Garmin email/password anywhere in this repo — Vercel env vars are the only place they should live. The function deliberately re-logs-in every run instead of caching a session token in Supabase, since that table's anon key is public (embedded in every page) — a cached token there would be readable by anyone who inspects the site's JS.

## Building from scratch

[BUILD_DASHBOARD.md](BUILD_DASHBOARD.md) is the prompt I gave Claude to generate `main.html` (the goals tracker) — paste it into Claude if you want to rebuild that page yourself.
