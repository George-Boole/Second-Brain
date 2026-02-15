# Second Brain

A personal knowledge management system that captures thoughts via Telegram, classifies them with AI, and stores them in a structured database.

## Overview

This system allows you to:
- Capture thoughts via Telegram text messages
- Auto-classify into categories (people, projects, ideas, admin)
- Store in Supabase (PostgreSQL) for retrieval
- Get daily digest summaries at 7 AM Mountain Time
- Complete, move, and delete items with inline buttons
- Multi-user support with isolated data per user
- One-tap admin approval for new users

## Project Structure

```
second-brain/
├── api/                    # Vercel serverless functions
│   ├── webhook.py          # Telegram webhook handler (main logic)
│   ├── capture.py          # POST endpoint for Siri Shortcuts (future)
│   └── cron/
│       ├── digest.py       # Morning digest (7 AM MT)
│       ├── evening.py      # Evening recap (9 PM MT)
│       ├── reminders.py    # Reminders check (2 PM MT)
│       └── weekly.py       # Weekly review (Sunday 1 PM MT)
├── bot/                    # Python bot modules
│   ├── classifier.py       # OpenAI classification + intent detection
│   ├── database.py         # Supabase operations + recurrence
│   ├── scheduler.py        # Digest/recap/weekly generation
│   └── config.py           # Environment configuration
├── database/               # SQL schemas
│   └── schema.sql          # PostgreSQL table definitions
├── prompts/                # AI prompts
│   ├── classification-prompt.txt
│   ├── daily-digest-prompt.txt
│   └── fix-handler-prompt.txt
├── docs/                   # Documentation
│   ├── adding-users.md     # How to add/manage users
│   ├── database-schema.md  # DB schema documentation
│   ├── multi-tenant-plan.md # Multi-tenant migration plan
│   ├── product-description.md # Full product description
│   ├── siri-shortcut.md    # Voice capture docs (future)
│   ├── test-messages.md    # Test data
│   └── archive/            # Legacy Slack/Make.com docs
├── vercel.json             # Vercel routing & cron config
├── requirements.txt        # Python dependencies
├── PROGRESS.md             # Build progress & session notes
└── RESUMING.md             # Quick-start guide for returning
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | List all commands |
| `/list` | View all active items |
| `/admin` | View admin tasks |
| `/projects` | View projects |
| `/people` | View people |
| `/ideas` | View ideas |
| `/digest` | Get daily digest now |
| `/review` | Classify needs_review items |
| `/someday` | View someday items |
| `/recap` | Evening recap |
| `/weekly` | Weekly review |
| `/settings` | View settings; changes are admin-only |
| `/myid` | Show your Telegram ID |
| `/invite <id> [name]` | Add a user (admin) |
| `/users` | List all users (admin) |
| `/remove <id>` | Deactivate a user (admin) |

## Special Message Formats

- `done: [task]` - Mark task complete
- `person: [msg]` - Force people category
- `project: [msg]` - Force projects category
- `idea: [msg]` - Force ideas category
- `admin: [msg]` - Force admin category
- Natural language: "I finished X" marks tasks done
- Natural language: "Remove X from projects" deletes items

## Technology Stack

- **Bot Platform:** Telegram
- **Deployment:** Vercel (serverless)
- **Database:** Supabase (PostgreSQL)
- **AI:** OpenAI GPT-4o
- **Language:** Python 3.11+

## Deployment

The bot is deployed on Vercel with:
- Webhook URL: `https://second-brain-one-orpin.vercel.app/api/webhook`
- Cron jobs run in UTC; all date logic uses user's configured timezone
- Auto-deploys on push to `main` branch

## Getting Started

See [PROGRESS.md](PROGRESS.md) for deployment details and session notes.

## Status

Deployed and running on Vercel.
