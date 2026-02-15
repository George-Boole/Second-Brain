# Second Brain Database Schema

Last Updated: 2026-02-15

## Overview

The Second Brain uses 10 PostgreSQL tables in Supabase to organize captured thoughts.

## Data Flow

```
Telegram Message → Vercel Webhook → AI Classification → inbox_log → Category Table
```

1. **Every message** first goes to `inbox_log` (audit trail)
2. AI classifies into a category with confidence score
3. Routes to the appropriate table
4. Original message stays in `inbox_log` for history

---

## Tables

### 1. inbox_log (Audit Trail)

**Purpose:** Complete history of every captured thought. Nothing is lost.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| created_at | Timestamp | When received |
| raw_message | Text | Original message text |
| source | Varchar | Where it came from (telegram, slack) |
| category | Varchar | AI classification result |
| confidence | Decimal | AI confidence (0.00-1.00) |
| ai_title | Varchar | AI-generated title |
| ai_response | JSONB | Full AI response |
| processed | Boolean | Was it routed? |
| target_table | Varchar | Which table it went to |
| target_id | UUID | ID in target table |

---

### 2. people (Contacts & Relationships)

**Purpose:** Track people you want to remember or follow up with.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| created_at | Timestamp | When created |
| updated_at | Timestamp | Last modified |
| name | Varchar | Person's name |
| relationship | Varchar | friend, colleague, client, etc. |
| email | Varchar | Optional email |
| phone | Varchar | Optional phone |
| notes | Text | Context about this person |
| last_contact | Date | When you last connected |
| follow_up_date | Date | When to reach out |
| follow_up_reason | Text | Why to reach out |
| **status** | Varchar | **active, completed** (default: active) |
| **completed_at** | Timestamp | **When marked complete** |
| inbox_log_id | UUID | Link to original message |

**Status values:**
- `active` - Person is actively tracked
- `completed` - Follow-up completed, archived for recaps

**Example:** "Remind me to call John about the project next week"

---

### 3. projects (Work & Goals)

**Purpose:** Track active work, goals, and initiatives.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| created_at | Timestamp | When created |
| updated_at | Timestamp | Last modified |
| title | Varchar | Project name |
| description | Text | What it's about |
| status | Varchar | active, paused, completed, someday |
| priority | Varchar | normal, high |
| due_date | Date | Deadline |
| completed_at | Timestamp | When marked complete |
| category | Varchar | work, personal, side-project |
| tags | Text[] | Array of tags |
| next_action | Text | What's the next step? |
| inbox_log_id | UUID | Link to original message |

**Status values:**
- `active` - Currently working on
- `paused` - On hold
- `completed` - Finished
- `someday` - Parked for later

**Example:** "I should really start that blog redesign project"

---

### 4. ideas (Thoughts & Inspiration)

**Purpose:** Capture fleeting thoughts before they disappear.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| created_at | Timestamp | When created |
| updated_at | Timestamp | Last modified |
| title | Varchar | Idea title |
| content | Text | Full idea description |
| category | Varchar | business, creative, learning |
| tags | Text[] | Array of tags |
| status | Varchar | active, captured, exploring, actionable, archived, someday |
| related_project | UUID | Optional link to project |
| inbox_log_id | UUID | Link to original message |

**Status values:**
- `active` - Default for new ideas (legacy: `captured`, `exploring`, `actionable` still supported in queries)
- `archived` - Completed or discarded
- `someday` - Parked for later

**Example:** "What if we used AI to automatically tag customer emails?"

---

### 5. admin (Tasks & To-Dos)

**Purpose:** Track administrative tasks and errands.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| created_at | Timestamp | When created |
| updated_at | Timestamp | Last modified |
| title | Varchar | Task name |
| description | Text | Details |
| status | Varchar | active, completed, someday |
| priority | Varchar | normal, high |
| due_date | Date | When it's due |
| completed_at | Timestamp | When marked complete |
| category | Varchar | errands, bills, appointments |
| inbox_log_id | UUID | Link to original message |

**Status values:**
- `active` - Not yet completed
- `completed` - Done
- `someday` - Parked for later

**Example:** "I need to renew my driver's license before March"

---

## Status Summary

All tables support completion tracking for recaps:

| Table | Active Status | Completed Status | Completed Field |
|-------|--------------|------------------|-----------------|
| admin | active | completed, someday | completed_at |
| projects | active, paused | completed, someday | completed_at |
| people | active | completed, someday | completed_at |
| ideas | active | archived, someday | completed_at |

---

## Category Classification

The AI classifies each message into one of these categories:

| Category | Routes To | Example |
|----------|-----------|---------|
| `people` | people table | "Catch up with Sarah" |
| `projects` | projects table | "Start the website redesign" |
| `ideas` | ideas table | "What if we tried X?" |
| `admin` | admin table | "Pay the electric bill" |
| `needs_review` | inbox_log only | Ambiguous messages (low confidence) |

**Confidence thresholds:**
- 0.6+ → Auto-categorize
- Below 0.6 → `needs_review` for manual classification

---

## Indexes

The following indexes are created for performance:

```sql
CREATE INDEX idx_inbox_log_created_at ON inbox_log(created_at);
CREATE INDEX idx_inbox_log_category ON inbox_log(category);
CREATE INDEX idx_admin_status ON admin(status);
CREATE INDEX idx_admin_due_date ON admin(due_date);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_people_status ON people(status);
CREATE INDEX idx_people_follow_up ON people(follow_up_date);
CREATE INDEX idx_ideas_status ON ideas(status);
```

---

## Row Level Security

RLS is enabled on all tables. The bot uses the `service_role` key which bypasses RLS. No per-role policies are defined (except via service_role bypass), so the `anon` key has no access to any table. This is intentional — all access goes through the bot's server-side code.

---

### 6. undo_log (Undo History)

**Purpose:** Store previous state before destructive actions for undo functionality.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| created_at | Timestamp | When action occurred |
| user_id | BigInt | Telegram user ID |
| action_type | Varchar | complete, delete, priority, date, status, move |
| table_name | Varchar | Which table was affected |
| item_id | UUID | ID of affected item |
| previous_data | JSONB | Full item state before action |

**Notes:**
- Keeps last 10 entries per user (auto-cleanup)
- Indexed on (user_id, created_at DESC) for fast lookup
- Supports restoring deleted items by re-inserting previous_data

---

### 7. users (Authorization)

**Purpose:** Track authorized bot users for multi-tenant support.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| telegram_id | BigInt | Telegram user ID (unique) |
| name | Varchar | Display name |
| is_admin | Boolean | Can manage other users |
| added_by | BigInt | Telegram ID of who invited them |
| created_at | Timestamp | When added |
| is_active | Boolean | Access enabled (default: true) |

**Notes:**
- Authorization is checked via database lookup (not env vars)
- Deactivating a user preserves their data but revokes access
- Admin commands: `/invite`, `/users`, `/remove`

---

### 8. edit_state (Text Input State)

**Purpose:** Track pending text edits (title/description changes via ForceReply).

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | BigInt | Telegram user ID |
| action | Varchar | edit_title or edit_desc |
| table_name | Varchar | Which table the item is in |
| item_id | UUID | ID of item being edited |
| created_at | Timestamp | When edit was initiated (5-min expiry) |

**Notes:**
- Used with Telegram's ForceReply to capture free-text input
- Entries expire after 5 minutes; expired edits are treated as new captures
- Cleaned up after successful edit

---

### 9. Multi-Tenant Columns

All data tables (admin, projects, people, ideas, inbox_log, settings, reminders, undo_log) have a `user_id BIGINT` column with indexes for per-user data isolation.

---

## Migrations Applied

1. **Initial schema** - Core 5 tables (admin, projects, people, ideas, inbox_log)
2. **add_status_to_people** (2026-02-01) - Added status and completed_at to people table
3. **add_settings_table** (2026-02-03) - Settings table for user preferences
4. **add_reminders_table** (2026-02-03) - Reminders table
5. **add_completed_at_to_ideas** (2026-02-03) - Completion tracking for ideas
6. **standardize_admin_status** (2026-02-04) - Changed admin statuses to active/completed/someday
7. **standardize_projects_priority** (2026-02-04) - Unified priority to normal/high
8. **add_priority_to_people** (2026-02-04) - Added priority column to people
9. **standardize_ideas** (2026-02-04) - Standardized ideas statuses
10. **add_recurrence_columns** (2026-02-04) - Added recurrence_pattern and is_recurring to admin, projects, people
11. **create_undo_log_table** (2026-02-06) - Undo log for reverting actions
12. **create_users_table** (2026-02-06) - Users table for multi-tenant auth
13. **add_user_id_to_all_tables** (2026-02-06) - user_id column on all data tables
14. **fix_medium_priority_to_normal** (2026-02-12) - Fixed leftover "medium" priority values
15. **create_edit_state_table** (2026-02-12) - Edit state for ForceReply text input
16. **enable_rls_edit_state** (2026-02-12) - RLS on edit_state table
17. **standardize_ideas_captured_to_active** (2026-02-12) - Changed ideas default status to "active"
18. **enable_rls_on_remaining_tables** (2026-02-15) - RLS on inbox_log, undo_log, users
19. **drop_make_automation_policy** (2026-02-15) - Removed overly permissive Make.com policy
