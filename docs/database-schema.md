# Second Brain Database Schema

## Overview

The Second Brain uses 5 PostgreSQL tables in Supabase to organize captured thoughts.

## Data Flow

```
Voice Message → Slack → Make.com → AI Classification → inbox_log → Category Table
```

1. **Every message** first goes to `inbox_log` (audit trail)
2. AI classifies into a category
3. Make.com routes to the appropriate table
4. Original message stays in `inbox_log` for history

---

## Tables

### 1. inbox_log (Audit Trail)

**Purpose:** Complete history of every captured thought. Nothing is lost.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| created_at | Timestamp | When received |
| raw_message | Text | Original voice transcription |
| source | Varchar | Where it came from (slack) |
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
| name | Varchar | Person's name |
| relationship | Varchar | friend, colleague, client, etc. |
| email | Varchar | Optional email |
| phone | Varchar | Optional phone |
| notes | Text | Context about this person |
| last_contact | Date | When you last connected |
| follow_up_date | Date | When to reach out |
| follow_up_reason | Text | Why to reach out |
| inbox_log_id | UUID | Link to original message |

**Example:** "Remind me to call John about the project next week"

---

### 3. projects (Work & Goals)

**Purpose:** Track active work, goals, and initiatives.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| title | Varchar | Project name |
| description | Text | What it's about |
| status | Varchar | active, paused, completed, archived |
| priority | Varchar | low, medium, high, urgent |
| due_date | Date | Deadline |
| category | Varchar | work, personal, side-project |
| tags | Text[] | Array of tags |
| next_action | Text | What's next? |
| inbox_log_id | UUID | Link to original message |

**Example:** "I should really start that blog redesign project"

---

### 4. ideas (Thoughts & Inspiration)

**Purpose:** Capture fleeting thoughts before they disappear.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| title | Varchar | Idea title |
| content | Text | Full idea description |
| category | Varchar | business, creative, learning |
| tags | Text[] | Array of tags |
| status | Varchar | captured, exploring, actionable |
| related_project | UUID | Optional link to project |
| inbox_log_id | UUID | Link to original message |

**Example:** "What if we used AI to automatically tag customer emails?"

---

### 5. admin (Tasks & To-Dos)

**Purpose:** Track administrative tasks and errands.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| title | Varchar | Task name |
| description | Text | Details |
| status | Varchar | pending, in_progress, completed |
| priority | Varchar | low, medium, high, urgent |
| due_date | Date | When it's due |
| category | Varchar | errands, bills, appointments |
| inbox_log_id | UUID | Link to original message |

**Example:** "I need to renew my driver's license before March"

---

## Category Classification

The AI classifies each message into one of these categories:

| Category | Routes To | Example |
|----------|-----------|---------|
| `people` | people table | "Catch up with Sarah" |
| `projects` | projects table | "Start the website redesign" |
| `ideas` | ideas table | "What if we tried X?" |
| `admin` | admin table | "Pay the electric bill" |
| `needs_review` | inbox_log only | Ambiguous messages |

---

## Setup Instructions

1. Go to your Supabase project
2. Open **SQL Editor**
3. Paste contents of `database/schema.sql`
4. Click **Run**
5. Verify tables in **Table Editor**

---

## Row Level Security

RLS is enabled on all tables. Configure policies based on your auth setup:
- For single-user: Allow all operations for authenticated users
- For multi-user: Add user_id columns and restrict by user
