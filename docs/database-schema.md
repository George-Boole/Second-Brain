# Second Brain Database Schema

Last Updated: 2026-02-06

## Overview

The Second Brain uses 8 PostgreSQL tables in Supabase to organize captured thoughts.

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
| status | Varchar | active, paused, completed, archived |
| priority | Varchar | low, medium, high, urgent |
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
- `archived` - Old/inactive

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
| status | Varchar | captured, exploring, actionable, archived |
| related_project | UUID | Optional link to project |
| inbox_log_id | UUID | Link to original message |

**Status values:**
- `captured` - Just recorded
- `exploring` - Thinking about it
- `actionable` - Ready to act on
- `archived` - Completed or discarded

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
| status | Varchar | pending, in_progress, completed |
| priority | Varchar | low, medium, high, urgent |
| due_date | Date | When it's due |
| completed_at | Timestamp | When marked complete |
| category | Varchar | errands, bills, appointments |
| inbox_log_id | UUID | Link to original message |

**Status values:**
- `pending` - Not started
- `in_progress` - Working on it
- `completed` - Done

**Example:** "I need to renew my driver's license before March"

---

## Status Summary

All tables support completion tracking for recaps:

| Table | Active Status | Completed Status | Completed Field |
|-------|--------------|------------------|-----------------|
| admin | pending, in_progress | completed | completed_at |
| projects | active, paused | completed, archived | completed_at |
| people | active | completed | completed_at |
| ideas | captured, exploring, actionable | archived | - |

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

RLS is enabled on all tables. The bot uses a service key that bypasses RLS.

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

### 8. Multi-Tenant Columns

All data tables (admin, projects, people, ideas, inbox_log, settings, reminders, undo_log) have a `user_id BIGINT` column with indexes for per-user data isolation.

---

## Migrations Applied

1. **Initial schema** - Core 5 tables
2. **add_status_to_people** (2026-02-01) - Added status and completed_at to people table
3. **create_undo_log_table** (2026-02-05) - Added undo_log table for undo functionality
4. **create_users_table** (2026-02-05) - Users table for multi-tenant authorization
5. **add_user_id_to_all_tables** (2026-02-05) - Added user_id column to all data tables
