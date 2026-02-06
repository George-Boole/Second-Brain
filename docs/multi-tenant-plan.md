# Multi-Tenant Migration Plan (Phase 13)

Last Updated: 2026-02-05
Status: PLANNING (not started)

## Overview

Add multi-user support so family members can each have isolated data while sharing the same bot and infrastructure.

## Architecture

- Single Telegram bot (shared)
- Single Supabase database (shared)
- Single Vercel deployment (shared)
- Data isolation via `user_id` column on all tables
- Each user sees only their own data

## Step-by-Step Plan

### Step 1: Database Migration
**Status:** NOT STARTED
**Files:** Supabase migrations

Add `user_id BIGINT` column to:
- [ ] admin
- [ ] projects
- [ ] people
- [ ] ideas
- [ ] inbox_log
- [ ] settings
- [ ] reminders
- [ ] undo_log

```sql
-- Migration: add_user_id_to_all_tables
ALTER TABLE admin ADD COLUMN IF NOT EXISTS user_id BIGINT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS user_id BIGINT;
ALTER TABLE people ADD COLUMN IF NOT EXISTS user_id BIGINT;
ALTER TABLE ideas ADD COLUMN IF NOT EXISTS user_id BIGINT;
ALTER TABLE inbox_log ADD COLUMN IF NOT EXISTS user_id BIGINT;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS user_id BIGINT;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS user_id BIGINT;
ALTER TABLE undo_log ADD COLUMN IF NOT EXISTS user_id BIGINT;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_admin_user_id ON admin(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_people_user_id ON people(user_id);
CREATE INDEX IF NOT EXISTS idx_ideas_user_id ON ideas(user_id);
CREATE INDEX IF NOT EXISTS idx_inbox_log_user_id ON inbox_log(user_id);
CREATE INDEX IF NOT EXISTS idx_settings_user_id ON settings(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
-- undo_log already has user_id index
```

Backfill with current user's ID (get from ALLOWED_USER_IDS[0]):
```sql
UPDATE admin SET user_id = YOUR_USER_ID WHERE user_id IS NULL;
UPDATE projects SET user_id = YOUR_USER_ID WHERE user_id IS NULL;
-- etc for all tables
```

---

### Step 2: database.py - Insert Functions
**Status:** NOT STARTED
**Files:** bot/database.py

Functions to update:
- [ ] `log_to_inbox(raw_message, source, classification)` → add user_id param
- [ ] `insert_person(classification, inbox_log_id)` → add user_id param
- [ ] `insert_project(classification, inbox_log_id)` → add user_id param
- [ ] `insert_idea(classification, inbox_log_id)` → add user_id param
- [ ] `insert_admin(classification, inbox_log_id)` → add user_id param
- [ ] `route_to_category(category, classification, inbox_log_id)` → add user_id param

Pattern:
```python
# Before
def insert_person(classification: dict, inbox_log_id: str) -> dict:
    data = { "name": ..., "inbox_log_id": inbox_log_id }

# After
def insert_person(classification: dict, inbox_log_id: str, user_id: int) -> dict:
    data = { "name": ..., "inbox_log_id": inbox_log_id, "user_id": user_id }
```

---

### Step 3: database.py - Basic Query Functions
**Status:** NOT STARTED
**Files:** bot/database.py

Functions to update:
- [ ] `get_all_active_items()` → add user_id param, filter all queries
- [ ] `get_someday_items()` → add user_id param
- [ ] `get_item_by_id(table, item_id)` → add user_id param (optional security filter)
- [ ] `find_task_by_title(title)` → add user_id param
- [ ] `find_item_for_deletion(search_term, table_hint)` → add user_id param
- [ ] `find_item_for_status_change(search_term)` → add user_id param
- [ ] `get_first_needs_review()` → add user_id param

Pattern:
```python
# Before
def get_all_active_items() -> dict:
    admin = supabase.table("admin").select("*").eq("status", "active").execute()

# After
def get_all_active_items(user_id: int) -> dict:
    admin = supabase.table("admin").select("*").eq("status", "active").eq("user_id", user_id).execute()
```

---

### Step 4: database.py - Scheduler Query Functions
**Status:** NOT STARTED
**Files:** bot/database.py

Functions to update:
- [ ] `get_active_projects()` → add user_id param
- [ ] `get_follow_ups()` → add user_id param
- [ ] `get_pending_admin()` → add user_id param
- [ ] `get_random_idea()` → add user_id param
- [ ] `get_needs_review()` → add user_id param
- [ ] `get_completed_today()` → add user_id param
- [ ] `get_tomorrow_priorities()` → add user_id param
- [ ] `get_overdue_items()` → add user_id param
- [ ] `get_completed_this_week()` → add user_id param
- [ ] `get_high_priority_items()` → add user_id param
- [ ] `get_random_someday_item()` → add user_id param

---

### Step 5: database.py - Update Functions
**Status:** NOT STARTED
**Files:** bot/database.py

Functions to update:
- [ ] `mark_task_done(table, task_id)` → add user_id param (for security)
- [ ] `delete_task(table, task_id)` → add user_id param
- [ ] `delete_item(inbox_log_id)` → add user_id param
- [ ] `move_item(source_table, item_id, dest_table)` → add user_id param
- [ ] `update_item_status(table, item_id, new_status)` → add user_id param
- [ ] `toggle_item_priority(table, item_id)` → add user_id param
- [ ] `update_item_date(table, item_id, new_date)` → add user_id param
- [ ] `update_item_title(table, item_id, new_title)` → add user_id param
- [ ] `update_item_description(table, item_id, new_desc)` → add user_id param
- [ ] `reclassify_item(inbox_log_id, new_category)` → add user_id param
- [ ] `update_inbox_log_processed(inbox_log_id, ...)` → add user_id param

---

### Step 6: database.py - Undo & Settings Functions
**Status:** NOT STARTED
**Files:** bot/database.py

Functions to update:
- [ ] `save_undo_state(user_id, ...)` → already has user_id!
- [ ] `get_last_undo(user_id)` → already has user_id!
- [ ] `execute_undo(user_id)` → already has user_id!
- [ ] `get_setting(key)` → add user_id param
- [ ] `set_setting(key, value)` → add user_id param
- [ ] `get_all_settings()` → add user_id param

Recurrence functions:
- [ ] `set_recurrence_pattern(table, item_id, pattern)` → add user_id param
- [ ] `clear_recurrence(table, item_id)` → add user_id param
- [ ] `create_recurring_task_copy(table, original_item, next_date)` → add user_id param

---

### Step 7: webhook.py - Command Handlers
**Status:** NOT STARTED
**Files:** api/webhook.py

Update `handle_command()` to pass user_id to all database calls:
- [ ] /list, /admin, /projects, /people, /ideas
- [ ] /someday
- [ ] /review
- [ ] /digest, /recap, /weekly
- [ ] /settings
- [ ] Message capture flow (classify → route)

---

### Step 8: webhook.py - Callback Handlers
**Status:** NOT STARTED
**Files:** api/webhook.py

Update `handle_callback()` to pass user_id to all database calls:
- [ ] done: (complete)
- [ ] delete:
- [ ] edit: (move menu)
- [ ] priority:
- [ ] date:/setdate:/pickdate:
- [ ] setsomeday:/setpause:/setactive:
- [ ] moveto:
- [ ] edit_title:/edit_desc:
- [ ] recur:/setrec:/clearrec:
- [ ] fix: (reclassify)
- [ ] undo:

Also update text input handling (EDIT_STATE responses).

---

### Step 9: Cron Jobs
**Status:** NOT STARTED
**Files:** api/cron/digest.py, evening.py, weekly.py, reminders.py

Update each cron to loop through users:
```python
# Before
async def send_morning_digest():
    digest = generate_digest()
    for user_id in ALLOWED_USER_IDS:
        await bot.send_message(chat_id=user_id, text=digest)

# After
async def send_morning_digest():
    for user_id in ALLOWED_USER_IDS:
        digest = generate_digest(user_id)  # Now personalized
        await bot.send_message(chat_id=user_id, text=digest)
```

Also update scheduler.py:
- [ ] `gather_digest_data()` → add user_id param
- [ ] `gather_evening_data()` → add user_id param
- [ ] `gather_weekly_data()` → add user_id param
- [ ] `generate_digest()` → add user_id param
- [ ] `generate_evening_recap()` → add user_id param
- [ ] `generate_weekly_review()` → add user_id param

---

### Step 10: Final Steps
**Status:** NOT STARTED
**Files:** Multiple

- [ ] Add `/myid` command (works for anyone, shows their Telegram ID)
- [ ] Update /help with multi-user info
- [ ] Test with current user (should work exactly as before)
- [ ] Update PROGRESS.md with Phase 13
- [ ] Update database-schema.md
- [ ] Update MEMORY.md

---

## Onboarding New Users

### Phase 1 Approach (Manual - env var)

After migration is complete:

1. New user finds bot in Telegram, sends `/start`
2. Bot says "Unauthorized" but shows their user ID via `/myid`
3. Admin adds their ID to `ALLOWED_USER_IDS` env var in Vercel
4. Vercel redeploys (~30 seconds)
5. New user sends `/start` again - works!

### Phase 2 Approach (Admin command - database-driven)

**Goal:** No redeploy needed to add users. Store allowed users in database.

**New table: `users`**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT UNIQUE NOT NULL,
    name VARCHAR(255),
    is_admin BOOLEAN DEFAULT FALSE,
    added_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
```

**New commands:**
- `/invite <telegram_id>` - Admin-only, adds a new user
- `/users` - Admin-only, lists all authorized users
- `/remove <telegram_id>` - Admin-only, deactivates a user

**Authorization flow change:**
```python
# Before (env var)
def is_authorized(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS

# After (database)
def is_authorized(user_id: int) -> bool:
    result = supabase.table("users").select("id").eq("telegram_id", user_id).eq("is_active", True).execute()
    return len(result.data) > 0
```

**Onboarding with /invite:**
1. New family member messages you their Telegram username
2. You look up their ID (or they use `/myid` on any bot)
3. You send: `/invite 123456789 Mom`
4. Bot confirms: "Added Mom (123456789). They can now use the bot!"
5. New user sends `/start` - works immediately, no redeploy!

**Optional: Invite links**
```
You: /createinvite
Bot: Share this link: t.me/YourBrainBot?start=invite_abc123
     (Expires in 24 hours, single use)

Family member clicks link → auto-registered
```

### Recommendation

- Implement Phase 1 first (manual env var) - gets multi-tenant working
- Phase 2 is a nice-to-have for convenience once you're adding multiple users

---

## Testing Checklist

- [ ] Existing data still accessible (backfill worked)
- [ ] New items get correct user_id
- [ ] /list shows only current user's items
- [ ] /digest is personalized
- [ ] Undo works (already had user_id)
- [ ] Settings are per-user
- [ ] Cron digests go to correct users with correct data

---

## Rollback Plan

If issues arise:
1. All queries still work if user_id is NULL (existing behavior)
2. Can remove user_id filters from code without removing columns
3. No data loss possible - only adding columns

