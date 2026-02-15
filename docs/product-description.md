# Second Brain - Product Description

## What It Is

Second Brain is a personal knowledge management system accessed through a chat interface. You send it any thought, idea, task, or note in plain language, and it automatically organizes it into the right category, stores it, and helps you stay on top of everything through scheduled summaries and one-tap actions.

It supports multiple users with completely isolated data, making it suitable for families or small teams who want to share the same system without seeing each other's information.

---

## Core Concept: Capture Everything, Organize Automatically

The fundamental interaction is simple: send a message, and the system handles the rest.

When you send a thought like "I need to renew my driver's license before March," the system uses AI to:

1. Classify it into the right category (in this case, an admin task)
2. Extract a title ("Renew driver's license")
3. Identify the due date (March)
4. Store it in the appropriate place
5. Confirm what was captured and let you correct the category if it got it wrong

You never need to think about where something goes. Just send it.

---

## The Four Buckets

Everything is organized into four categories:

### Admin
Tasks, errands, and to-dos. Things that need to get done.
- "Pay the electric bill by Friday"
- "Schedule dentist appointment"
- "Return the package at the post office"

### Projects
Active work, goals, and initiatives. Larger efforts that have next steps.
- "Start the blog redesign project"
- "Plan the family vacation for June"
- "Research new car options"

### People
Contacts and relationships you want to maintain. Follow-ups and check-ins.
- "Catch up with Sarah about her new job"
- "Call Mom on her birthday next Tuesday"
- "Follow up with the contractor about the estimate"

### Ideas
Fleeting thoughts and inspiration. Things worth remembering that aren't actionable yet.
- "What if we hosted a neighborhood block party?"
- "App idea: a shared grocery list that learns what you buy"
- "Book recommendation from podcast: Thinking Fast and Slow"

If the AI isn't confident about a classification (below 60% confidence), the item goes to a review queue where you can manually assign it.

---

## Viewing and Managing Items

### Lists

You can view your items in several ways:
- **All active items** across every bucket at once
- **A single bucket** (just admin tasks, just projects, etc.)
- **Someday items** - things you've parked for later

Each item in a list shows:
- A status indicator showing urgency (green for healthy, yellow for due soon, red for overdue)
- A high-priority flag if set
- The item title
- Contextual info (due date, next action for projects, follow-up date for people)

### Actions Per Item

Every item in a list has three one-tap actions:
- **Edit** - opens a menu with full editing options
- **Complete** - marks it done
- **Delete** - removes it permanently

### Edit Menu

Tapping an item's name opens a detailed edit menu (as a separate message so the list stays visible):

**Edit fields:**
- Change the title
- Change the description

**Properties:**
- Toggle priority between normal and high
- Set a due date (with quick options like "today," "tomorrow," "+3 days," "+1 week," or a full calendar picker with month navigation)
- Set a recurrence pattern

**Move and status:**
- Move the item to a different bucket (admin, projects, people, or ideas)
- Set status to "someday" (park it for later)
- Pause a project (projects only)
- Reactivate a someday or paused item

### Undo

Every list includes an undo button at the bottom. It reverts the last action you took - whether that was completing, deleting, changing priority, changing a date, or changing status. The system keeps the last 10 actions available to undo per user.

---

## Natural Language Understanding

Beyond simple capture, the system understands intent from natural language:

### Completing Tasks
Say "I called Rachel" and the system recognizes this as completing the "Call Rachel" task. Other examples:
- "I finished the report"
- "Done with the grocery shopping"
- You can also use the explicit format: "done: task name"

### Deleting Items
- "Remove Call Sarah from projects"
- "Delete the dentist appointment"
- The system asks for confirmation before deleting

### Status Changes
- "Pause project X" - sets a project to paused
- "Resume project X" - reactivates it
- "Move X to someday" - parks any item for later

### Forcing a Category
If you want to override the AI classification, prefix your message:
- "person: John Smith - met at conference, follow up next week"
- "project: Website redesign"
- "idea: What if we tried a different approach?"
- "admin: Buy groceries"

---

## Recurring Tasks

Tasks, projects, and people follow-ups can be set to recur automatically. When you complete a recurring item, the system creates the next occurrence with the appropriate future date. The original stays in your completed history.

Supported patterns:
- **Daily** - every day
- **Weekly** - a specific day of the week (Monday, Tuesday, etc.)
- **Biweekly** - every other week on a specific day
- **Monthly by date** - the same day each month (e.g., the 15th)
- **Monthly by pattern** - first Monday, first Tuesday, last day of month, etc.

You can set or change recurrence from the edit menu, and clear it at any time.

---

## Scheduled Reports

The system sends automated reports on a daily schedule:

### Morning Digest (Daily)
A summary to start your day:
- Active projects with their next actions
- People you need to follow up with
- Pending admin tasks
- A random idea for inspiration ("spark")
- Items that need your review

### Evening Recap (Daily)
A look back at your day:
- Everything you completed today
- Tomorrow's priorities and focus items
- Overdue items that need attention

### Weekly Review (Sundays)
A broader perspective:
- Everything accomplished in the past 7 days
- High-priority items across all buckets
- A random "someday" item surfaced for reconsideration

All reports can also be triggered on demand at any time.

---

## Priority and Urgency

### Priority Levels
Every item has a priority: **normal** (default) or **high**. High-priority items are flagged visually and included in report summaries.

### Urgency Indicators
Items with due dates show color-coded urgency:
- **Green** - 4 or more days until due (or no due date)
- **Yellow** - due within 0-3 days
- **Red** - overdue

---

## Multi-User Support

### Data Isolation
Multiple users can share the same system. Each user's data is completely isolated - they only see their own items, get their own reports, and manage their own tasks.

### Onboarding
Adding a new user is simple:
1. The new person sends any message to the system
2. The system replies with a welcome message and notifies all administrators
3. An administrator sees the request with the person's name and a one-tap "Invite" button
4. Tapping "Invite" approves the user immediately
5. The new user receives a confirmation and can start using the system right away

Administrators can also invite users directly by ID if preferred.

### User Management
- **Invite** - add a new user (admin only)
- **List users** - see all users with active/inactive status (admin only)
- **Remove** - deactivate a user, revoking access but preserving their data (admin only)

Deactivated users can be re-invited later and their data will still be there.

### Roles
- **Users** can capture, view, edit, complete, and delete their own items. They can view system settings.
- **Administrators** can do everything users can, plus manage other users and change system settings (timezone, report delivery times).

---

## Settings

System settings are shared across all users and can only be changed by administrators:
- **Timezone** - determines when scheduled reports are delivered
- **Morning digest hour** - when the daily digest goes out
- **Evening recap hour** - when the evening recap goes out

Any user can view the current settings.

---

## Audit Trail

Every message sent to the system is logged in a complete audit trail, regardless of how it's classified or where it ends up. This provides:
- A history of everything you've ever captured
- The original message text alongside the AI's classification
- Confidence scores for each classification
- Links from the log to where each item was routed

---

## Voice Capture (Future Feature)

Voice capture via Siri Shortcuts is planned but not yet working. A `/api/capture` endpoint exists on the server side, but the iOS Shortcuts integration needs further debugging. For now, use iOS dictation within the Telegram keyboard as a workaround.
