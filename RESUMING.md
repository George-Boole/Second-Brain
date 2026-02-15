# Resuming the Second Brain Project

Last Updated: 2026-02-15

Use this guide to get back up to speed after a break.

---

## What Is This?

A **Telegram bot** that captures your thoughts via chat, auto-classifies them with AI (OpenAI GPT-4o) into 4 buckets (Admin tasks, Projects, People, Ideas), and stores them in **Supabase** (PostgreSQL). Deployed as a **Vercel** serverless function.

---

## Current State: Stable & Running

The bot is **deployed and working** in production. No active bugs. All features complete through Phase 15.

- **Vercel URL:** `https://second-brain-one-orpin.vercel.app`
- **Webhook:** `https://second-brain-one-orpin.vercel.app/api/webhook`
- **Supabase project:** `obqqvdaccfzejpjitgnk`
- **GitHub:** `https://github.com/George-Boole/Second-Brain` (auto-deploys on push to `main`)
- **Branch:** `main` (only branch)

---

## Architecture at a Glance

```
User sends Telegram message
  -> Vercel webhook (api/webhook.py)
    -> AI classifies message (bot/classifier.py)
    -> Stores in Supabase (bot/database.py)
    -> Returns confirmation with fix-category buttons

Cron jobs (api/cron/*.py)
  -> Run daily at fixed UTC times
  -> Generate reports per user (bot/scheduler.py)
  -> Send via Telegram Bot API
```

**Key files:**
| File | Purpose |
|------|---------|
| `api/webhook.py` | Main handler: commands, messages, button callbacks, edit state |
| `bot/database.py` | All Supabase operations, recurrence logic, undo system |
| `bot/classifier.py` | OpenAI classification + intent detection (completion, deletion, status change) |
| `bot/scheduler.py` | Generates digest, recap, weekly review content |
| `bot/config.py` | Environment variables and security config |

---

## Database: 10 Tables

All tables have `user_id` column for multi-tenant isolation. RLS enabled on all tables.

| Table | Purpose |
|-------|---------|
| `admin` | Tasks and to-dos |
| `projects` | Work, goals, initiatives |
| `people` | Contacts and follow-ups |
| `ideas` | Fleeting thoughts |
| `inbox_log` | Audit trail of every message |
| `settings` | Per-user timezone/schedule prefs |
| `reminders` | Reminder entries |
| `undo_log` | Previous state for undo (last 10 per user) |
| `edit_state` | Pending ForceReply text edits (5-min expiry) |
| `users` | Authorization: who can use the bot |

**Status values:** `active`, `completed`, `someday` (+ `paused` for projects)
**Priority:** `normal` or `high` (never "medium" or "low")
**People quirk:** Uses `name` (not `title`), `notes` (not `description`), `follow_up_date` (not `due_date`)

---

## Multi-User System

- **Auth is database-driven** via `users` table (not env vars)
- Bot uses `service_role` key (bypasses RLS)
- Greg is seeded admin (Telegram ID: 8329742042)
- New user flow: user messages bot -> admins get "Invite" button -> one tap to approve
- Admin commands: `/myid`, `/invite`, `/users`, `/remove`

---

## Key Patterns to Remember

- **Callback data** must stay under 64 bytes (Telegram limit). Format: `action:table:item_id[:extra]`
- **Edit menu** opens as a NEW message (keeps list visible), deleted after action
- **Text input** (title/description edits) uses Supabase `edit_state` table + Telegram `ForceReply`
- **Undo** saves state before destructive actions, keeps last 10 per user
- **Recurrence** on complete: creates a new task copy with future date, original stays completed
- **Timezone:** Always use `_get_local_today(user_id)` or `_get_user_today(user_id)`, never `date.today()`
- **Timezone in queries:** Timestamps compared against `timestamptz` columns MUST include UTC offset (e.g., `-07:00`)

---

## Cron Schedule

| Job | UTC Time | Mountain Time | File |
|-----|----------|---------------|------|
| Morning Digest | 14:00 daily | 7:00 AM | `api/cron/digest.py` |
| Reminders | 21:00 daily | 2:00 PM | `api/cron/reminders.py` |
| Evening Recap | 04:00 daily | 9:00 PM | `api/cron/evening.py` |
| Weekly Review | 20:00 Sun | 1:00 PM Sun | `api/cron/weekly.py` |

Note: Vercel Hobby plan only supports daily cron. All users share the same schedule.

---

## Known Issues / Future Work

- **Voice capture via Siri Shortcuts:** `/api/capture` endpoint exists and works server-side, but iOS Shortcuts "Get Contents of URL" can't reach it. Needs Vercel log investigation.
- **`should_send_now()` in cron files** is dead code (exists but not called)
- **Supabase Security Advisor info items:** "RLS Enabled No Policy" on most tables. This is fine — `service_role` bypasses RLS, and having no policies blocks the `anon` key (correct behavior).

---

## How to Make Changes

1. Edit code locally
2. `git add <files> && git commit -m "message"`
3. `git push` -> Vercel auto-deploys from `main`
4. Test by messaging the bot in Telegram

**Environment variables** are set in Vercel dashboard (not in code):
- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY` (service_role key)

---

## Documentation Map

| File | What's in it |
|------|-------------|
| `PROGRESS.md` | Full build history, all phases, session notes |
| `RESUMING.md` | This file - quick catch-up guide |
| `README.md` | Project overview and structure |
| `docs/database-schema.md` | Complete DB schema with all 10 tables |
| `docs/product-description.md` | User-facing feature description |
| `docs/adding-users.md` | How to invite/manage users |
| `docs/multi-tenant-plan.md` | Multi-tenant migration plan (complete) |
| `docs/siri-shortcut.md` | Voice capture status (not yet working) |
