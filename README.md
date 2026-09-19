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
| [lock.js](lock.js) | Login gate — shows a Supabase Auth email/password screen and hides the page until signed in |
| [section-template.html](section-template.html) | Starter template for a new page/section — same design system + cloud sync, ready to copy |

Each app stores its own state in browser `localStorage`. No accounts, no server — except for the login gate and cloud sync described below.

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

You'll also need a `public.app_state` table (key text primary key, data jsonb, updated_at timestamptz) — see **Login / access control** below for the RLS policies, since access is restricted to a logged-in user rather than left open to `anon`.

## Login / access control

Every page loads [lock.js](lock.js) right after the Supabase CDN script, which hides the page and shows an email/password login screen until you're signed in via Supabase Auth. This isn't just a UI gate — the underlying `app_state` table's RLS policies are restricted to the `authenticated` role, so even someone who finds this repo's (public) Supabase URL + key can't read or write your data without actually logging in.

Setup, in order (**do this before relying on the login screen** — until you've created a user, you won't be able to get past it):

1. In Supabase → **Authentication → Sign In / Providers**: confirm **Email** is enabled, and **turn off "Allow new users to sign up"** (and "Allow anonymous sign-ins" if present) so nobody but you can ever create an account.
2. **Authentication → Users → Add user**: create yourself an account (your email + a password only you know).
3. In the **SQL Editor**, lock down the data table to logged-in users only:
   ```sql
   do $$
   declare pol record;
   begin
     for pol in select policyname from pg_policies where schemaname='public' and tablename='app_state'
     loop
       execute format('drop policy %I on public.app_state', pol.policyname);
     end loop;
   end $$;

   create policy "authenticated select app_state"
     on public.app_state for select to authenticated using (true);
   create policy "authenticated insert app_state"
     on public.app_state for insert to authenticated with check (true);
   create policy "authenticated update app_state"
     on public.app_state for update to authenticated using (true) with check (true);
   ```
4. Once logged in on a device, the session persists (localStorage) across every page on the dashboard — you only log in once per browser.

**Known gap:** gym progress photos (`storage.objects`, bucket `progress-photos`) are still on a public bucket with `anon` policies from the Cloud sync setup section above — they weren't locked down in this pass. The bucket's `public: true` flag means files are reachable via their public URL regardless of `storage.objects` RLS, so properly closing this off would mean switching the bucket to private and `gym.html` to signed URLs instead of `getPublicUrl()`.

## Garmin sync setup (optional)

[api/garmin-sync.py](api/garmin-sync.py) is a Vercel Python serverless function that logs into Garmin Connect once a day (via [vercel.json](vercel.json)'s cron config) and writes resting heart rate, body battery and sleep into the `garmin` row of the same `app_state` table — [health.html](health.html)'s "Vitals" card reads it from there.

It uses the unofficial [`garminconnect`](https://pypi.org/project/garminconnect/) library (there's no realistic path to Garmin's official Developer API for a personal project — that requires business approval). To turn it on:

1. In your Vercel project → **Settings → Environment Variables**, add:
   - `GARMIN_EMAIL` — your Garmin Connect login email
   - `GARMIN_PASSWORD` — your Garmin Connect login password
   - `CRON_SECRET` — any random string (Vercel automatically sends this back as a bearer token when it triggers the cron job, so the public function URL can't be used by randoms to trigger a Garmin login)
2. Redeploy. The cron in `vercel.json` runs daily at 09:00 UTC — edit the schedule string if you want a different time.
3. To test it immediately rather than waiting for the cron, visit `https://<your-app>.vercel.app/api/garmin-sync` with an `Authorization: Bearer <your CRON_SECRET>` header (e.g. `curl -H "Authorization: Bearer <secret>" https://.../api/garmin-sync`).

**Note on credentials:** never put your Garmin email/password anywhere in this repo — Vercel env vars are the only place they should live. The function deliberately re-logs-in every run instead of caching a session token in Supabase, to avoid adding another sensitive value to that table even though it's now locked to `authenticated` access (see **Login / access control** above).

## Building from scratch

[BUILD_DASHBOARD.md](BUILD_DASHBOARD.md) is the prompt I gave Claude to generate `main.html` (the goals tracker) — paste it into Claude if you want to rebuild that page yourself.
