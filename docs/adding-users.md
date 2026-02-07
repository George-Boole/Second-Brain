# Adding Users to Second Brain

## Overview

Second Brain supports multiple users, each with their own isolated data. Only admins can manage users. Currently, Greg is the sole admin.

## How New Users Get Added

### Automatic Flow (Recommended)

1. A new user opens the bot in Telegram and sends **any message** (or `/start`)
2. The bot replies: "Welcome! I've notified the admin. You'll be able to use the bot once they approve."
3. All admins receive a notification with the user's name and an **Invite** button
4. An admin taps **Invite** - the user is immediately added
5. The new user receives a welcome message and can start using the bot

No need to exchange Telegram IDs manually!

### Manual Flow

Admins can also invite users directly if they know their Telegram ID:

```
/invite <telegram_id> <name>
```

**Example:**
```
/invite 123456789 Mom
```

Users can find their Telegram ID by sending `/myid` to the bot (works for anyone).

## Managing Users

### List All Users

```
/users
```

Shows all users with status indicators:
- Green circle = active
- Red circle = deactivated
- Crown = admin

### Remove a User

```
/remove <telegram_id>
```

This **deactivates** the user (revokes access) but **preserves their data**. They can be re-invited later with `/invite` and their data will still be there.

## Important Notes

- Only admins can run `/invite`, `/users`, and `/remove`
- New users are never created as admins
- You cannot remove yourself
- Each user's data is completely isolated - they only see their own items
- Cron jobs (digests, recaps, reminders) automatically include all active users
