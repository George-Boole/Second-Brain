# Second Brain Build Progress

Last Updated: 2026-02-03
Current Phase: Complete (Maintenance Mode)
Branch: main

## Status: DEPLOYED & RUNNING ON VERCEL

> **Note:** Legacy Slack + Make.com implementation docs are preserved in `docs/archive/slack-make-implementation/`

## Completed Phases:

### Phase 1-3: Setup & Core Code ✅
- Created branch: telegram-bot
- Bot scaffold with all core files
- Telegram setup with @BotFather
- All credentials saved

### Phase 4: Replit Deployment ✅ (Deprecated)
- Originally deployed to Replit
- Migrated to Vercel in Phase 6

### Phase 5: Feature Enhancements ✅

#### 5.1 Inline Fix Buttons ✅
- Every captured message shows category buttons to fix misclassification
- Buttons reclassify and move items between tables
- Cancel button to delete mistaken entries

#### 5.2 Daily Digest ✅
- `/digest` command for on-demand digest
- Scheduled daily at 7 AM Mountain Time (via Vercel Cron)
- AI-formatted summary includes:
  - Active projects with next actions
  - People to contact (with follow_up_date)
  - Pending admin tasks
  - Random "spark" idea
  - Items needing review

#### 5.3 Review Command ✅
- `/review` shows needs_review items one at a time
- Category buttons to classify
- Auto-advances to next item after fixing

#### 5.4 Natural Language Completion ✅
- AI detects completion intent in messages
- "I called Rachel" → marks "Call Rachel" as done
- Falls back to normal capture if no matching task

#### 5.5 Natural Language Deletion ✅
- AI detects deletion intent in messages
- "Remove Call Sarah from projects" → finds and deletes
- Confirmation prompt before deleting
- Table hints supported (from projects, from admin, etc.)

#### 5.6 Improved Classification ✅
- Better date extraction ("today", "tomorrow" → actual dates)
- Clearer people vs admin rules:
  - Contact/follow-up tasks → people (with follow_up_date)
  - Impersonal tasks → admin (with due_date)
- Current date passed to AI for accurate date calculation

### Phase 6: Vercel Migration ✅
- Migrated from Replit (long-polling) to Vercel (serverless/webhook)
- Converted bot to webhook architecture
- Set up Vercel Cron for daily digest (7 AM Mountain Time)
- Connected GitHub repo for auto-deployments

### Phase 7: Enhanced Item Management ✅ (2026-02-01)
- Added `/list` command to view all active items across buckets
- Added individual bucket commands: `/admin`, `/projects`, `/people`, `/ideas`
- Three action buttons per item:
  - ✅ Complete - marks item done (sets status='completed')
  - ⇄ Move - reclassify to different bucket
  - 🗑 Delete - permanently remove item
- After any action, bucket re-lists with remaining items
- Added status field to people table for tracking completions
- All tables now have consistent status tracking for future recaps
- Removed `/tasks` command (functionality merged into `/list` and bucket commands)

## Bot Commands:
| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | List all commands |
| `/list` | View all active items (all buckets) |
| `/admin` | View admin tasks |
| `/projects` | View projects |
| `/people` | View people |
| `/ideas` | View ideas |
| `/digest` | Get daily digest now |
| `/review` | Classify needs_review items |

## Special Message Formats:
- `done: [task]` - Mark task complete
- `person: [msg]` - Force people category
- `project: [msg]` - Force projects category
- `idea: [msg]` - Force ideas category
- `admin: [msg]` - Force admin category
- Natural language: "I finished X" marks tasks done
- Natural language: "Remove X from projects" deletes items (with confirmation)

## Inline Buttons:
- **On new captures:** Category buttons + Cancel (delete)
- **On list items:** ✅ Complete | ⇄ Move | 🗑 Delete
- **On move:** Destination bucket selection + Cancel

## Database Schema:

### All tables have status tracking:
| Table | Status Values | Default |
|-------|--------------|---------|
| admin | pending, in_progress, completed | pending |
| projects | active, paused, completed, archived | active |
| people | active, completed | active |
| ideas | captured, exploring, actionable, archived | captured |

### Tables also track:
- `created_at` - when item was created
- `completed_at` - when item was marked complete (for recaps)
- `inbox_log_id` - link back to original message

## Files Structure:
```
bot/
├── bot.py          # Original bot (for Replit - deprecated)
├── classifier.py   # AI classification + completion/deletion detection
├── database.py     # Supabase operations + task management
├── scheduler.py    # Daily digest generation
├── config.py       # Environment + security config
├── requirements.txt
└── .env            # Local credentials (gitignored)

api/                # Vercel serverless functions
├── webhook.py      # Telegram webhook handler (main logic)
└── cron/
    └── digest.py   # Scheduled daily digest

vercel.json         # Vercel routes + cron config
requirements.txt    # Root-level deps for Vercel
```

## Key Functions in database.py:
- `log_to_inbox()` - audit trail for all messages
- `route_to_category()` - insert into appropriate table
- `mark_task_done()` - set status=completed
- `delete_task()` - permanently delete item
- `move_item()` - transfer between tables
- `get_all_active_items()` - fetch non-completed items
- `find_item_for_deletion()` - search for items by title
- `reclassify_item()` - move item between categories

## Key Functions in classifier.py:
- `classify_message()` - AI categorization with confidence scoring
- `detect_completion_intent()` - recognize "I did X" statements
- `detect_deletion_intent()` - recognize "Remove X" requests

## Credentials (in bot/.env locally, Vercel Environment Variables for deployment):
- TELEGRAM_BOT_TOKEN - from @BotFather
- SUPABASE_URL - https://obqqvdaccfzejpjitgnk.supabase.co
- SUPABASE_SERVICE_KEY - stored in .env / Vercel
- OPENAI_API_KEY - stored in .env / Vercel

## Vercel Deployment:
- Repository: https://github.com/George-Boole/Second-Brain
- Branch: main
- Production URL: https://second-brain-one-orpin.vercel.app
- Webhook URL: https://second-brain-one-orpin.vercel.app/api/webhook
- Auto-deploys on push to main branch
- Cron job runs daily at 14:00 UTC (7 AM Mountain Time)

## Resume Instructions:
Say "let's resume the second brain project" - deployed to Vercel from `main` branch.

## Session Notes:

### 2026-02-03:
- Refactored list view commands (`/list`, `/admin`, etc.) to use a single `build_bucket_list` function.
- Attempted to redesign the button layout for list items based on feedback.
- Current implementation uses a 4-column button layout.
- **PAUSED:** Pausing work on the button layout. The current implementation in the `main` branch is not the desired final state. Further discussion is needed on how to best handle button widths within Telegram's UI constraints.

### 2026-02-01:
- Added Cancel button to classification choices (deletes mistaken entries)
- Added Delete buttons to /tasks and list views
- Added natural language deletion with confirmation ("Remove X from Y")
- Added /list command showing all active items
- Added /admin, /projects, /people, /ideas bucket commands
- Added Move (reclassify) buttons to list items
- Added Complete buttons - all items now have ✅ ⇄ 🗑 buttons
- Removed /tasks command (merged into /list)
- Added status field to people table (migration applied)
- All buckets now track completed_at for future recaps
- Fixed "Message is not modified" Telegram API errors

### 2026-01-31:
- Migrated from Replit to Vercel successfully
- Fixed natural language task completion (more aggressive past-tense detection)
- Merged telegram-bot-vercel into main, deleted old branches

## Future Enhancements (Not Yet Started):

### List & Display Improvements
- [ ] Show status indicator on list items (pending/active/in_progress)
- [ ] Show due dates prominently in list views
- [ ] Color coding or emoji for overdue items

### Scheduling & Notifications
- [ ] Evening recap - summary of what was completed today
- [ ] Recurring messages - ability to set repeating reminders (daily, weekly, monthly)
- [ ] Customizable digest times

### Voice Features
- [ ] Voice transcription (Whisper API) - capture voice messages
- [ ] Voice readback of digest (Telegram voice message API)

### Reporting & Review
- [ ] Weekly review command
- [ ] Recap reports (completed items by date range)
- [ ] Productivity stats (items completed per week/month)

### Other
- [ ] Web dashboard for viewing/editing items
- [ ] Search command to find items across all buckets
- [ ] Snooze/postpone items to a future date
