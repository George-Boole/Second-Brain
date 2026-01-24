# Second Brain - Quick Build Guide
## For Claude Code CLI

**Target Repository:** `C:\Users\greg\OneDrive\Dev\nate-jones\second-brain\`
**Build Time:** 2-3 hours total
**Approach:** Step-by-step with state preservation

---

## CRITICAL INSTRUCTIONS FOR CLAUDE CODE CLI

### State Preservation Protocol

**ALWAYS maintain PROGRESS.md with:**
- Current step number
- What was just completed
- What's next
- Any credentials or decisions made (non-sensitive)
- Timestamp of last update

**Update PROGRESS.md after EVERY step** so if we crash or take a break, we can resume exactly where we left off.

**Format:**
```markdown
Last Updated: [timestamp]
Current Step: [N]
Current Phase: [Phase Name]

Completed:
- [x] Step 1: [name] - [timestamp]
- [x] Step 2: [name] - [timestamp]

Next: Step [N+1]: [name]

Session Notes:
- [Any important context]
```

---

## BUILD PHASES (15 Steps Total, ~2-3 hours)

### PHASE 1: Repository & Database (30 min)

**Step 1: Initialize Repository Structure**
- Create folder structure: `docs/`, `database/`, `config/`, `prompts/`, `make-scenarios/`
- Create PROGRESS.md, README.md, .gitignore
- **Output:** Organized repo ready

**Step 2: Create Database Schema**
- Create `database/schema.sql` with 5 tables:
  - inbox_log (audit trail)
  - people (contacts)
  - projects (work)
  - ideas (thoughts)
  - admin (tasks)
- Create `docs/database-schema.md` explaining structure
- **Output:** SQL file ready to execute

**Step 3: User Executes Schema in Supabase**
- Guide user to run schema.sql in Supabase SQL Editor
- User confirms tables created
- Save Supabase URL and anon key to `config/.env.example` (as placeholder)
- **Output:** Database tables exist

---

### PHASE 2: Slack Setup (20 min)

**Step 4: Document Slack Setup**
- Create `docs/slack-setup.md` with instructions:
  - Create workspace at slack.com/create
  - Create #sb-inbox channel
  - Test voice message
- **Output:** Setup guide created

**Step 5: User Creates Slack Workspace**
- User follows guide
- Creates workspace
- Creates #sb-inbox channel
- Tests voice message → confirms transcription works
- **Output:** Slack workspace ready

---

### PHASE 3: ChatGPT Prompt (20 min)

**Step 6: Create Classification Prompt**
- Create `prompts/classification-prompt.txt` with prompt:
```
Classify into: people, projects, ideas, admin, needs_review
Return JSON: {"category": "...", "confidence": 0.85, "title": "..."}
```
- Create 5 test messages in `docs/test-messages.md`
- **Output:** Prompt ready

**Step 7: User Tests Prompt**
- User tests in ChatGPT Playground
- Confirms valid JSON returned
- Confirms categories correct
- **Output:** Prompt validated

---

### PHASE 4: Make.com Capture Flow (45 min)

**Step 8: Create Capture Flow Blueprint**
- Create `docs/make-capture-flow.md` documenting:
  1. Slack Watch Messages trigger
  2. ChatGPT classification
  3. Parse JSON
  4. Insert to inbox_log
  5. Router by category
  6. Insert to category table
  7. Send Slack confirmation
- Include field mappings for each step
- **Output:** Complete blueprint

**Step 9-10: User Builds in Make.com (Guided)**
- Guide user through each module
- One module at a time
- Test after each addition
- Export scenario to `make-scenarios/capture-flow.json`
- **Output:** Working capture flow

**Step 11: End-to-End Test**
- User sends voice message
- Verify appears in Supabase
- Verify Slack confirmation
- **Output:** System captures thoughts!

---

### PHASE 5: Daily Digest (30 min)

**Step 12: Create Digest Prompt**
- Create `prompts/daily-digest-prompt.txt`
- Create `database/digest-queries.sql` with:
  - Active projects query
  - Upcoming people follow-ups
  - Pending admin tasks
- **Output:** Digest components ready

**Step 13: User Builds Daily Digest in Make.com**
- Guide through:
  1. Schedule trigger (7am daily)
  2. 3x Supabase Select queries
  3. ChatGPT digest generation
  4. Slack message
- Export to `make-scenarios/daily-digest.json`
- **Output:** Daily digest working

---

### PHASE 6: Documentation (15 min)

**Step 14: Create Setup Guide**
- Create `SETUP_GUIDE.md` with:
  - How to reproduce entire system
  - All Make.com scenarios documented
  - Troubleshooting section
- **Output:** Complete reproduction guide

**Step 15: Final Commit**
- Git add all files
- Commit with message: "Second Brain system v1.0"
- Update README.md with overview
- **Output:** Everything in git

---

## QUICK START FOR CLAUDE CODE CLI

**To start building:**

1. Open terminal in: `C:\Users\greg\OneDrive\Dev\nate-jones\second-brain\`
2. Start Claude Code CLI
3. Give this command:

```
Read BUILD_GUIDE.md and execute it step-by-step.

CRITICAL:
- Update PROGRESS.md after EVERY step
- Wait for my confirmation before proceeding
- If I say "break", save state and stop
- If I say "resume", read PROGRESS.md and continue

Start with Step 1.
```

---

**Ready to build? Start Claude Code CLI in this directory and give it the Quick Start command!**
