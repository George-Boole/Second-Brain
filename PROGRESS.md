# Second Brain Build Progress

Last Updated: 2026-02-05
Current Phase: Complete (Maintenance Mode)
Branch: main

## Status: DEPLOYED & RUNNING ON VERCEL

> **Note:** Legacy Slack + Make.com implementation docs are preserved in `docs/archive/slack-make-implementation/`

## Completed Phases:

### Phase 1-3: Setup & Core Code
- Created branch: telegram-bot
- Bot scaffold with all core files
- Telegram setup with @BotFather
- All credentials saved

### Phase 4: Replit Deployment (Deprecated)
- Originally deployed to Replit
- Migrated to Vercel in Phase 6

### Phase 5: Feature Enhancements

#### 5.1 Inline Fix Buttons
- Every captured message shows category buttons to fix misclassification
- Buttons reclassify and move items between tables
- Cancel button to delete mistaken entries

#### 5.2 Daily Digest
- `/digest` command for on-demand digest
- Scheduled daily at 7 AM Mountain Time (via Vercel Cron)
- AI-formatted summary includes:
  - Active projects with next actions
  - People to contact (with follow_up_date)
  - Pending admin tasks
  - Random "spark" idea
  - Items needing review

#### 5.3 Review Command
- `/review` shows needs_review items one at a time
- Category buttons to classify
- Auto-advances to next item after fixing

#### 5.4 Natural Language Completion
- AI detects completion intent in messages
- "I called Rachel" marks "Call Rachel" as done
- Falls back to normal capture if no matching task

#### 5.5 Natural Language Deletion
- AI detects deletion intent in messages
- "Remove Call Sarah from projects" finds and deletes
- Confirmation prompt before deleting
- Table hints supported (from projects, from admin, etc.)

#### 5.6 Natural Language Status Changes
- "Pause project X" sets status to paused
- "Resume project X" sets status to active
- "Move X to someday" parks items for later

### Phase 6: Vercel Migration
- Migrated from Replit (long-polling) to Vercel (serverless/webhook)
- Converted bot to webhook architecture
- Set up Vercel Cron for scheduled reports
- Connected GitHub repo for auto-deployments

### Phase 7: Enhanced Item Management (2026-02-01)
- Added `/list` command to view all active items across buckets
- Added individual bucket commands: `/admin`, `/projects`, `/people`, `/ideas`
- Action buttons per item with move/complete/delete functionality
- Status field tracking across all tables

### Phase 8: Unified Status & Priority Model (2026-02-04)
- **Standardized statuses across all buckets:**
  - admin: active, completed, someday
  - projects: active, paused, completed, someday
  - people: active, completed, someday
  - ideas: active, archived, someday
- **Priority system:** normal (default) or high (flagged with ⚡)
- **Status indicators based on urgency:**
  - 🟢 Green: active or 4+ days to due date
  - 🟡 Yellow: due within 0-3 days
  - 🔴 Red: overdue
  - ⏸ Pause icon for paused projects
  - ⚡ Lightning bolt for high priority

### Phase 9: Scheduled Reports & Settings (2026-02-04)
- **Evening Recap** (`/recap`): Summary of day's completions, tomorrow's priorities
- **Weekly Review** (`/weekly`): Week's accomplishments, high priority items, someday surfacing
- **Cron schedules:**
  - Morning digest: 7 AM MT daily
  - Evening recap: 9 PM MT daily
  - Reminders check: 2 PM MT daily
  - Weekly review: 1 PM MT Sundays
- **Settings command** (`/settings`): Configure timezone, digest/recap hours

### Phase 10: Enhanced Button UX (2026-02-04)
- **Button row per item:** [#] [✅] [⚡/○] [📅] [✏] [🗑]
  - ✅ Mark complete
  - ⚡/○ Toggle priority (high/normal)
  - 📅 Date picker (admin, projects, people only)
  - ✏ Edit/move menu
  - 🗑 Delete
- **Edit/move menu shows:**
  - Item title for clarity
  - ✏️ Title / 📝 Description edit buttons
  - 🔄 Recurrence (admin, projects, people)
  - All bucket destinations
  - 💭 Someday option (all buckets)
  - 🟢 Active (for someday/paused items)
  - ⏸ Pause (projects only)
- **Date picker with calendar:**
  - Quick options: Today, Tomorrow, +3 days, +1 week, Clear
  - Full calendar picker with month navigation
  - Today highlighted with dots
- **All acknowledgments show item title:**
  - "*Item Name*\nMarked complete!"

## Bot Commands:
| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | List all commands and features |
| `/list` | View all active items (all buckets) |
| `/admin` | View admin tasks |
| `/projects` | View projects |
| `/people` | View people |
| `/ideas` | View ideas |
| `/someday` | View items parked for "someday" |
| `/digest` | Get morning digest now |
| `/recap` | Get evening recap now |
| `/weekly` | Get weekly review now |
| `/review` | Classify needs_review items |
| `/settings` | View/change settings (timezone, hours) |

## Special Message Formats:
- `done: [task]` - Mark task complete
- `person: [msg]` - Force people category
- `project: [msg]` - Force projects category
- `idea: [msg]` - Force ideas category
- `admin: [msg]` - Force admin category

## Natural Language Support:
- "I finished X" / "I called Sarah" - marks tasks done
- "Remove X from projects" - deletes items (with confirmation)
- "Pause project X" - sets project to paused
- "Resume project X" - sets project to active
- "Move X to someday" - parks item for later

## Inline Buttons:
- **On new captures:** Category buttons + Cancel (delete)
- **On list items:** [Edit/Item] | ✅ | 🗑 + ↩️ Undo row at bottom
- **On edit menu (separate message):** ✏ Title | 📝 Description | ⚡ Priority | 📅 Date | 🔄 Recurrence | Bucket moves | Status changes
- **On recurrence picker:** Daily | Weekday selector | Monthly | Biweekly | Clear
- **On date picker:** Quick dates + Calendar + Clear

## Database Schema:

### Status Values:
| Table | Statuses | Default |
|-------|----------|---------|
| admin | active, completed, someday | active |
| projects | active, paused, completed, someday | active |
| people | active, completed, someday | active |
| ideas | active, archived, someday | active |

### Priority:
All tables have `priority` field: `normal` (default) or `high`

### Date Fields:
- admin: `due_date`
- projects: `due_date`
- people: `follow_up_date`
- ideas: no date field

### Timestamps:
- `created_at` - when item was created
- `completed_at` - when item was marked complete
- `inbox_log_id` - link back to original message

## Files Structure:
```
bot/
├── classifier.py   # AI classification + intent detection
├── database.py     # Supabase operations + item management + recurrence
├── scheduler.py    # Digest, recap, weekly review generation
├── config.py       # Environment + security config
├── requirements.txt
└── .env            # Local credentials (gitignored)

api/                # Vercel serverless functions
├── webhook.py      # Telegram webhook handler (main logic, edit state, recurrence UI)
└── cron/
    ├── digest.py   # Morning digest (7 AM MT)
    ├── evening.py  # Evening recap (9 PM MT)
    ├── reminders.py # Reminders check (2 PM MT)
    └── weekly.py   # Weekly review (Sunday 1 PM MT)

docs/
└── siri-shortcut.md  # Voice capture via Siri Shortcuts

vercel.json         # Vercel routes + cron config
requirements.txt    # Root-level deps for Vercel
```

## Key Functions:

### database.py:
- `log_to_inbox()` - audit trail for all messages
- `route_to_category()` - insert into appropriate table
- `mark_task_done()` - set status=completed, handles recurring task creation
- `delete_task()` - permanently delete item
- `move_item()` - transfer between tables
- `get_all_active_items()` - fetch non-completed items
- `get_someday_items()` - fetch someday items
- `update_item_status()` - change status (active/paused/someday)
- `toggle_item_priority()` - switch between normal/high
- `update_item_date()` - set due_date/follow_up_date
- `get_item_by_id()` - fetch single item
- `update_item_title()` - edit item title/name
- `update_item_description()` - edit item description/content/notes
- `set_recurrence_pattern()` - set recurring task pattern
- `clear_recurrence()` - remove recurrence from item
- `calculate_next_occurrence()` - compute next date from pattern
- `create_recurring_task_copy()` - create new task for next occurrence
- `save_undo_state()` - store item state before destructive action
- `get_last_undo()` - retrieve most recent undo entry for user
- `execute_undo()` - revert last action (complete, delete, priority, date, status)

### classifier.py:
- `classify_message()` - AI categorization with confidence scoring
- `detect_completion_intent()` - recognize "I did X" statements
- `detect_deletion_intent()` - recognize "Remove X" requests
- `detect_status_change_intent()` - recognize "Pause/Resume X"

### scheduler.py:
- `generate_digest()` - morning digest
- `generate_evening_recap()` - evening summary
- `generate_weekly_review()` - weekly accomplishments

## Vercel Deployment:
- Repository: https://github.com/George-Boole/Second-Brain
- Branch: main
- Production URL: https://second-brain-one-orpin.vercel.app
- Webhook URL: https://second-brain-one-orpin.vercel.app/api/webhook
- Auto-deploys on push to main branch

### Cron Schedules (UTC):
| Job | UTC Time | Mountain Time |
|-----|----------|---------------|
| Digest | 14:00 | 7:00 AM |
| Evening | 04:00 | 9:00 PM |
| Reminders | 21:00 | 2:00 PM |
| Weekly | 20:00 Sun | 1:00 PM Sun |

## Resume Instructions:
Say "let's resume the second brain project" - deployed to Vercel from `main` branch.

### Phase 11: Edit, Recurring Tasks & Voice (2026-02-04)
- **Edit Item Menu:** ⇄ button replaced with ✏ Edit menu
  - Edit title via ForceReply text input
  - Edit description via ForceReply text input
  - In-memory state dict with 5-minute timeout
  - Seamless: type response goes to edit, expired state captures as new item
- **Recurring Tasks:**
  - Database migration: added `recurrence_pattern` and `is_recurring` columns to admin, projects, people
  - Recurrence patterns: daily, weekly:N (Mon-Sun), biweekly:N, monthly:N, monthly:last, monthly:first_mon/tue/etc
  - On task completion: auto-creates next occurrence with future date
  - Recurrence picker UI with day selection, biweekly, monthly submenus
  - Next occurrence notification shown on completion
  - Clear recurrence option
- **Voice Capture via Siri Shortcuts:**
  - Setup documentation at `docs/siri-shortcut.md`
  - "Hey Siri, Second Brain" → dictate → auto-sends to bot
  - No code changes needed (uses native Telegram Send Message action)

### Phase 12: Simplified Buttons & Undo (2026-02-05)
- **Simplified list layout:** 3 columns (Edit, Complete, Delete)
  - Removed redundant Edit column (was duplicate of Item click)
  - Renamed "Item" column to "Edit"
- **List stays visible:** Edit menu now opens as separate message
  - Original list remains visible while editing
  - Menu is deleted after action, fresh list sent
- **Undo functionality:**
  - New `undo_log` table stores previous state before actions
  - ↩️ Undo button at bottom of every list
  - Supports: complete, delete, priority, date, status changes
  - Keeps last 10 undo entries per user
  - Restores deleted items, reverts status changes
- **Evening recap fix:** People with high priority now included in "Tomorrow's Focus"

## Session Notes:

### 2026-02-05:
- Fixed evening recap missing high-priority people items
- Simplified list to 3 columns (Edit, Complete, Delete)
- Edit menu now opens as separate message (list stays visible)
- Added undo functionality with undo_log table
- Undo button appears on all lists, reverts last action
- Updated /help to reflect new button layout

### 2026-02-04:
- Major schema reorganization: unified status model across all buckets
- Added priority field (normal/high) to all buckets with ⚡ display
- Added /someday command and someday status option
- Added /weekly command and Sunday cron for weekly review
- Added /recap command for evening recap
- Added /settings command for timezone and schedule configuration
- Enhanced list buttons: priority toggle (⚡/○), date picker (📅)
- Added calendar picker with month navigation for date selection
- Move menu now shows item title and context-aware status options
- All acknowledgment messages now show item title
- Status indicators: 🟢 (active/4+ days), 🟡 (0-3 days), 🔴 (overdue)
- Updated /help to document all features

### 2026-02-03:
- Added status emoji indicators based on due date urgency
- Sorted admin tasks by due date (nearest first)
- Fixed list alignment for 10+ items
- Added evening recap with completed_today, tomorrow's priorities
- Added ideas to completed_today tracking

### 2026-02-01:
- Added /list and bucket commands with action buttons
- Added natural language deletion with confirmation
- All tables now track completed_at for recaps

### 2026-01-31:
- Migrated from Replit to Vercel successfully
- Fixed natural language task completion

### Phase 13: Multi-Tenant Support (PLANNED)
- **Goal:** Allow family members to use the same bot with isolated data
- **Approach:** Add `user_id` column to all tables, filter all queries
- **Detailed plan:** See `docs/multi-tenant-plan.md`
- **10 implementation steps:**
  1. Database migration (add user_id columns)
  2. database.py - insert functions
  3. database.py - basic query functions
  4. database.py - scheduler query functions
  5. database.py - update functions
  6. database.py - undo & settings functions
  7. webhook.py - command handlers
  8. webhook.py - callback handlers
  9. Cron jobs
  10. Add /myid command, test, update docs

## Future Enhancements (Not Yet Started):

### Voice Features
- [ ] Voice transcription (Whisper API) - capture voice messages
- [x] Voice capture via Siri Shortcuts (docs/siri-shortcut.md)
- [ ] Voice readback of digest (Telegram voice message API)

### Reporting & Review
- [ ] Recap reports (completed items by date range)
- [ ] Productivity stats (items completed per week/month)

### Other
- [ ] Web dashboard for viewing/editing items
- [ ] Search command to find items across all buckets
- [ ] Snooze/postpone items to a future date
- [x] Recurring tasks with auto-regeneration on completion
- [ ] Duplicate detection and management
