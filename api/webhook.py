"""Vercel serverless function for Telegram webhook."""

import json
import logging
import sys
import os
from datetime import date, datetime

# Add bot directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bot'))

from http.server import BaseHTTPRequestHandler
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup

from config import TELEGRAM_BOT_TOKEN, validate_config
from classifier import classify_message, detect_completion_intent, detect_deletion_intent, detect_status_change_intent
from database import (
    log_to_inbox, route_to_category, update_inbox_log_processed, reclassify_item,
    get_first_needs_review, mark_task_done, find_task_by_title,
    delete_item, delete_task, find_item_for_deletion, get_all_active_items, move_item,
    get_setting, set_setting, get_all_settings,
    update_item_status, find_item_for_status_change, get_someday_items, toggle_item_priority,
    get_item_by_id, update_item_date, update_item_title, update_item_description,
    set_recurrence_pattern, clear_recurrence, calculate_next_occurrence,
    save_undo_state, execute_undo, get_last_undo,
    is_user_authorized, is_user_admin, add_user, list_users, deactivate_user,
)
from scheduler import generate_digest, generate_evening_recap, generate_weekly_review

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Category emoji mapping
CATEGORY_EMOJI = {
    "people": "\U0001F464",
    "projects": "\U0001F4CB",
    "ideas": "\U0001F4A1",
    "admin": "\U00002705",
    "needs_review": "\U0001F914",
}

# Status emoji mapping for list view (simplified unified model)
STATUS_EMOJI = {
    "admin": {"active": "\U0001F7E2"},      # green circle
    "projects": {"active": "\U0001F7E2", "paused": "\u23F8"},  # green/pause
    "ideas": {"active": "\U0001F4A1"},      # lightbulb
    "people": {"active": "\U0001F7E2"},     # green circle
}

# High priority flag
PRIORITY_FLAG = "\u26A1"  # ⚡ lightning bolt for high priority

CATEGORIES = ["people", "projects", "ideas", "admin"]

# Edit state tracking for text input (title/description editing)
# Format: {user_id: {"action": "edit_title"|"edit_desc", "table": str, "item_id": str, "timestamp": datetime}}
EDIT_STATE = {}
EDIT_STATE_TIMEOUT_MINUTES = 5


def clean_expired_edit_states():
    """Remove edit states older than timeout."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(minutes=EDIT_STATE_TIMEOUT_MINUTES)
    expired = [uid for uid, state in EDIT_STATE.items() if state.get("timestamp", datetime.min) < cutoff]
    for uid in expired:
        del EDIT_STATE[uid]


def format_date_relative(date_str):
    """Format date as relative string (today, tomorrow, in 3 days, overdue!)"""
    if not date_str:
        return None
    try:
        if isinstance(date_str, str):
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target = date_str
    except ValueError:
        return date_str
    delta = (target - date.today()).days
    if delta < 0:
        return "overdue!"
    elif delta == 0:
        return "today"
    elif delta == 1:
        return "tomorrow"
    elif delta <= 7:
        return f"in {delta} days"
    return target.strftime("%b %d")


def get_date_urgency_emoji(date_str):
    """Get emoji based on due date urgency.
    - Green: 4+ days away or no date
    - Yellow: 0-3 days (today to 3 days from now)
    - Red: overdue
    """
    if not date_str:
        return "\U0001F7E2"  # Green - no due date
    try:
        if isinstance(date_str, str):
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target = date_str
    except ValueError:
        return "\U0001F7E2"  # Green - invalid date
    delta = (target - date.today()).days
    if delta < 0:
        return "\U0001F534"  # Red - overdue
    elif delta <= 3:
        return "\U0001F7E1"  # Yellow - 0-3 days
    else:
        return "\U0001F7E2"  # Green - 4+ days


def build_calendar_keyboard(table: str, item_id: str, year: int, month: int) -> list:
    """Build a calendar keyboard for date picking."""
    import calendar

    # Month header with navigation
    month_name = calendar.month_name[month]
    keyboard = [[
        InlineKeyboardButton(text="◀", callback_data=f"cal:{table}:{item_id}:{year}:{month}:prev"),
        InlineKeyboardButton(text=f"{month_name} {year}", callback_data="noop"),
        InlineKeyboardButton(text="▶", callback_data=f"cal:{table}:{item_id}:{year}:{month}:next"),
    ]]

    # Day headers
    keyboard.append([
        InlineKeyboardButton(text=d, callback_data="noop")
        for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    ])

    # Get calendar for this month
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    month_days = cal.monthdayscalendar(year, month)

    today = date.today()

    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
            else:
                # Highlight today
                day_date = date(year, month, day)
                day_str = f"•{day}•" if day_date == today else str(day)
                row.append(InlineKeyboardButton(
                    text=day_str,
                    callback_data=f"pickdate:{table}:{item_id}:{year}-{month:02d}-{day:02d}"
                ))
        keyboard.append(row)

    # Cancel button - pass table for list re-render
    keyboard.append([InlineKeyboardButton(text="\u274C Cancel", callback_data=f"cancel_edit:{table}")])

    return keyboard


def build_fix_keyboard(inbox_log_id: str, current_category: str) -> list:
    """Build inline keyboard data for category fix buttons."""
    buttons = []
    for cat in CATEGORIES:
        if cat != current_category:
            emoji = CATEGORY_EMOJI.get(cat, "")
            buttons.append(InlineKeyboardButton(
                text=f"{emoji} {cat}",
                callback_data=f"fix:{inbox_log_id}:{cat}"
            ))
    # Arrange in 2x2 grid
    keyboard = [buttons[:2], buttons[2:]] if len(buttons) > 2 else [buttons]
    # Add cancel button on its own row
    keyboard.append([InlineKeyboardButton(
        text="\u274C Cancel (delete)",
        callback_data=f"cancel:{inbox_log_id}"
    )])
    return keyboard


def build_bucket_list(bucket: str, action_msg: str = None, all_items: dict = None, user_id: int = None) -> tuple:
    """
    Build text and keyboard for a bucket list.
    Returns (text, keyboard) tuple.
    If user_id is provided and all_items is None, fetches items for that user.
    """
    items = all_items if all_items is not None else get_all_active_items(user_id)
    bucket_items = items.get(bucket, [])

    if not bucket_items:
        text = action_msg + "\n\n" if action_msg else ""
        text += f"_No more items in {bucket}._"
        return (text, None)

    emoji = CATEGORY_EMOJI.get(bucket, "")
    text = action_msg + "\n\n" if action_msg else ""
    text += f"*{emoji} {bucket.title()}:*\n"
    buttons = []

    # Column header row (3 columns: Edit, Complete, Delete)
    header_row = [
        InlineKeyboardButton(text="Edit                                  ", callback_data="noop"),
        InlineKeyboardButton(text="Complete", callback_data="noop"),
        InlineKeyboardButton(text="Delete", callback_data="noop"),
    ]
    buttons.append(header_row)

    for i, item in enumerate(bucket_items, 1):
        # Get title (people use 'name', others use 'title')
        title = item.get('name') or item.get('title', 'Untitled')
        status = item.get('status', '')
        priority = item.get('priority', 'normal')

        # Get date and check if overdue
        date_field = item.get('due_date') if bucket in ['admin', 'projects'] else item.get('follow_up_date')
        formatted_date = format_date_relative(date_field) if date_field else None
        is_overdue = formatted_date == "overdue!"

        # Status emoji - admin uses date-based urgency, others use status-based
        if bucket == "admin":
            status_emoji = get_date_urgency_emoji(date_field)
        elif bucket == "people" and is_overdue:
            status_emoji = "\U0001F534"  # Red for overdue follow-up
        else:
            status_emoji = STATUS_EMOJI.get(bucket, {}).get(status, "")

        # High priority flag
        priority_flag = f" {PRIORITY_FLAG}" if priority == "high" else ""

        # Build line (pad number for alignment)
        num = f"{i:2d}." if len(bucket_items) >= 10 else f"{i}."
        text += f"{num} {status_emoji}{priority_flag} {title}" if status_emoji else f"{num}{priority_flag} {title}"

        # Add contextual info
        if bucket == "admin" and formatted_date:
            text += f" _({formatted_date})_"
        elif bucket == "projects":
            if status == 'paused':
                text += " _(paused)_"
            elif formatted_date:
                text += f" _({formatted_date})_"
            if item.get('next_action'):
                text += f"\n  ↳ Next: {item['next_action'][:50]}"
        elif bucket == "people" and formatted_date:
            text += f" _(follow up: {formatted_date})_"
        elif bucket == "ideas" and status in ['exploring', 'actionable']:
            text += f" _({status})_"
        text += "\n"

        # Title in first column (tapping opens edit), action buttons are narrow
        status_prefix = f"{status_emoji} " if status_emoji else ""
        row = [
            InlineKeyboardButton(text=f"{i}. {status_prefix}{priority_flag}{title[:28]}", callback_data=f"edit:{bucket}:{item['id']}"),
            InlineKeyboardButton(text="\u2705", callback_data=f"done:{bucket}:{item['id']}"),
            InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delete:{bucket}:{item['id']}")
        ]
        buttons.append(row)

    # Add Undo button at the bottom
    buttons.append([InlineKeyboardButton(text="\u21A9\uFE0F Undo", callback_data=f"undo:{bucket}")])

    keyboard = InlineKeyboardMarkup(buttons) if buttons else None
    return (text, keyboard)


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized via database lookup."""
    return is_user_authorized(user_id)


async def handle_command(bot: Bot, chat_id: int, command: str, user_id: int):
    """Handle bot commands."""
    if not is_authorized(user_id):
        await bot.send_message(chat_id=chat_id, text="Unauthorized. This bot is private.")
        return

    if command == "/start":
        welcome = (
            "Welcome to Second Brain!\n\n"
            "Send me any thought, idea, or note and I'll:\n"
            "1. Classify it (people/projects/ideas/admin)\n"
            "2. Store it in your database\n"
            "3. Confirm what was captured\n\n"
            "Tips:\n"
            "- Start with 'person:', 'project:', 'idea:', or 'admin:' to force a category\n"
            "- Just send text messages anytime\n\n"
            "Try it now - send me a thought!"
        )
        await bot.send_message(chat_id=chat_id, text=welcome)

    elif command == "/help":
        help_text = (
            "*Second Brain Commands:*\n\n"
            "*View Items:*\n"
            "/list - All active items (all buckets)\n"
            "/admin - Admin tasks only\n"
            "/projects - Projects only\n"
            "/people - People only\n"
            "/ideas - Ideas only\n"
            "/someday - Items saved for \"someday\"\n\n"
            "*Digests & Reports:*\n"
            "/digest - Morning digest (priorities, overdue)\n"
            "/recap - Evening recap (today's wins)\n"
            "/weekly - Weekly review (accomplishments)\n"
            "/review - Classify needs\\_review items\n\n"
            "*Settings:*\n"
            "/settings - View current settings\n"
            "/settings timezone America/Denver\n"
            "/settings morning 7\n"
            "/settings evening 21\n\n"
            "*User Management:*\n"
            "/myid - Show your Telegram ID\n"
            "/invite <id> [name] - Add a user (admin)\n"
            "/users - List all users (admin)\n"
            "/remove <id> - Deactivate a user (admin)\n\n"
            "*Category Prefixes:*\n"
            "`person:` `project:` `idea:` `admin:`\n"
            "Forces category when capturing\n\n"
            "*Natural Language Examples:*\n"
            "`done: task name` - Mark complete\n"
            "\"I called Sarah\" - Marks task done\n"
            "\"Remove X from projects\" - Deletes entry\n"
            "\"Pause project X\" - Status to paused\n"
            "\"Resume project X\" - Status to active\n"
            "\"Move X to someday\" - Park for later\n\n"
            "*Status Indicators:*\n"
            "\U0001F7E2 Active (or 4+ days to due)\n"
            "\U0001F7E1 Due within 3 days\n"
            "\U0001F534 Overdue\n"
            "\u23F8 Paused (projects only)\n"
            "\u26A1 High priority\n\n"
            "*List Buttons (3 columns):*\n"
            "Edit \u2022 Complete \u2022 Delete\n"
            "\u2022 Tap item name \u2192 Opens edit menu\n"
            "\u2022 \u2705 \u2192 Mark complete\n"
            "\u2022 \U0001F5D1 \u2192 Delete permanently\n"
            "\u2022 \u21A9\uFE0F Undo \u2192 Revert last action\n\n"
            "*Edit Menu (opens as popup):*\n"
            "\u2022 \u270F\uFE0F Title / \U0001F4DD Description\n"
            "\u2022 \u26A1 Priority toggle\n"
            "\u2022 \U0001F4C5 Date picker\n"
            "\u2022 \U0001F504 Set recurrence\n"
            "\u2022 Move to bucket\n"
            "\u2022 \U0001F4AD someday / \u23F8 pause / \U0001F7E2 active\n\n"
            "_Send any message to capture a thought!_"
        )
        await bot.send_message(chat_id=chat_id, text=help_text, parse_mode="Markdown")

    elif command == "/digest":
        await bot.send_message(chat_id=chat_id, text="Generating your digest...")
        try:
            digest = generate_digest(user_id)
            await bot.send_message(chat_id=chat_id, text=digest, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error generating digest: {e}")
            await bot.send_message(chat_id=chat_id, text=f"Error generating digest: {str(e)}")

    elif command == "/review":
        item = get_first_needs_review(user_id)
        if not item:
            await bot.send_message(chat_id=chat_id, text="All caught up! No items need review.")
            return

        text = (
            f"*Needs Review*\n\n"
            f"*Title:* {item.get('ai_title', 'Unknown')}\n"
            f"*Message:* {item.get('raw_message', '')[:200]}\n"
            f"*Confidence:* {float(item.get('confidence', 0)):.0%}\n\n"
            f"Tap a category to classify:"
        )
        keyboard = InlineKeyboardMarkup(build_fix_keyboard(item["id"], "needs_review"))
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

    elif command == "/list":
        items = get_all_active_items(user_id)
        total = sum(len(v) for v in items.values())

        if total == 0:
            await bot.send_message(chat_id=chat_id, text="No active items in any bucket.")
            return

        # Send each bucket as a separate message
        for bucket in CATEGORIES:
            if items.get(bucket):
                text, keyboard = build_bucket_list(bucket, all_items=items, user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

        await bot.send_message(chat_id=chat_id, text=f"_Total: {total} active items_", parse_mode="Markdown")

    elif command in ["/admin", "/projects", "/people", "/ideas"]:
        bucket = command[1:]
        text, keyboard = build_bucket_list(bucket, user_id=user_id)
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

    elif command == "/recap":
        await bot.send_message(chat_id=chat_id, text="Generating evening recap...")
        try:
            recap = generate_evening_recap(user_id)
            await bot.send_message(chat_id=chat_id, text=recap, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error generating recap: {e}")
            await bot.send_message(chat_id=chat_id, text=f"Error generating recap: {str(e)}")

    elif command == "/weekly":
        await bot.send_message(chat_id=chat_id, text="Generating weekly review...")
        try:
            weekly = generate_weekly_review(user_id)
            await bot.send_message(chat_id=chat_id, text=weekly, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error generating weekly review: {e}")
            await bot.send_message(chat_id=chat_id, text=f"Error generating weekly review: {str(e)}")

    elif command == "/someday":
        items = get_someday_items(user_id)
        total = sum(len(v) for v in items.values())

        if total == 0:
            await bot.send_message(chat_id=chat_id, text="No someday items! Use natural language like \"move X to someday\" to add items.")
            return

        await bot.send_message(chat_id=chat_id, text=f"*\U0001F4AD Someday/Maybe ({total} items):*", parse_mode="Markdown")
        for bucket in CATEGORIES:
            if items.get(bucket):
                text, keyboard = build_bucket_list(bucket, all_items=items, user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

    elif command == "/users":
        if not is_user_admin(user_id):
            await bot.send_message(chat_id=chat_id, text="This command is admin-only.")
            return

        users = list_users()
        if not users:
            await bot.send_message(chat_id=chat_id, text="No users found.")
            return

        text = "*Authorized Users:*\n\n"
        for u in users:
            status = "\U0001F7E2" if u.get("is_active") else "\U0001F534"
            admin_badge = " \U0001F451" if u.get("is_admin") else ""
            name = u.get("name") or "Unknown"
            tid = u.get("telegram_id")
            text += f"{status}{admin_badge} {name} (`{tid}`)\n"

        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

    elif command == "/settings" or command.startswith("/settings "):
        # Handle settings command - need full text for arguments
        pass  # Will be handled in handle_message for full text access


async def handle_settings_command(bot: Bot, chat_id: int, text: str, user_id: int):
    """Handle /settings command with optional arguments."""
    parts = text.split(maxsplit=2)

    if len(parts) == 1:
        # Show current settings
        settings = get_all_settings(user_id)
        msg = "*\u2699\uFE0F Settings:*\n"
        msg += f"\u2022 Timezone: `{settings.get('timezone', 'America/Denver')}`\n"
        msg += f"\u2022 Morning digest: `{settings.get('morning_digest_hour', '7')}:00`\n"
        msg += f"\u2022 Evening recap: `{settings.get('evening_recap_hour', '21')}:00`\n\n"
        msg += "_Commands:_\n"
        msg += "`/settings timezone America/Denver`\n"
        msg += "`/settings morning 7`\n"
        msg += "`/settings evening 21`"
        await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    elif len(parts) >= 2:
        key_map = {"timezone": "timezone", "morning": "morning_digest_hour", "evening": "evening_recap_hour"}
        setting_key = key_map.get(parts[1])

        if not setting_key:
            await bot.send_message(chat_id=chat_id, text="Unknown setting. Use: timezone, morning, or evening")
        elif len(parts) < 3:
            current = get_setting(setting_key, user_id)
            await bot.send_message(chat_id=chat_id, text=f"Current {parts[1]}: `{current}`\n\nUsage: `/settings {parts[1]} <value>`", parse_mode="Markdown")
        else:
            set_setting(setting_key, parts[2], user_id)
            await bot.send_message(chat_id=chat_id, text=f"\u2705 Updated {parts[1]} to `{parts[2]}`", parse_mode="Markdown")


async def handle_admin_command(bot: Bot, chat_id: int, text: str, user_id: int):
    """Handle admin commands (/invite, /remove)."""
    if not is_user_admin(user_id):
        await bot.send_message(chat_id=chat_id, text="This command is admin-only.")
        return

    parts = text.split(maxsplit=2)
    command = parts[0]

    if command == "/invite":
        if len(parts) < 2:
            await bot.send_message(chat_id=chat_id, text="Usage: `/invite <telegram_id> [name]`", parse_mode="Markdown")
            return

        try:
            target_id = int(parts[1])
        except ValueError:
            await bot.send_message(chat_id=chat_id, text="Invalid Telegram ID. Must be a number.")
            return

        name = parts[2] if len(parts) > 2 else None
        result = add_user(target_id, name, added_by=user_id)
        if result:
            display_name = name or str(target_id)
            await bot.send_message(
                chat_id=chat_id,
                text=f"\u2705 Added *{display_name}* (`{target_id}`). They can now use the bot!",
                parse_mode="Markdown"
            )
        else:
            await bot.send_message(chat_id=chat_id, text="Failed to add user. Please try again.")

    elif command == "/remove":
        if len(parts) < 2:
            await bot.send_message(chat_id=chat_id, text="Usage: `/remove <telegram_id>`", parse_mode="Markdown")
            return

        try:
            target_id = int(parts[1])
        except ValueError:
            await bot.send_message(chat_id=chat_id, text="Invalid Telegram ID. Must be a number.")
            return

        if target_id == user_id:
            await bot.send_message(chat_id=chat_id, text="You can't remove yourself!")
            return

        success = deactivate_user(target_id)
        if success:
            await bot.send_message(
                chat_id=chat_id,
                text=f"\u274C User `{target_id}` has been deactivated. Their data is preserved.",
                parse_mode="Markdown"
            )
        else:
            await bot.send_message(chat_id=chat_id, text="User not found or already deactivated.")


async def handle_message(bot: Bot, chat_id: int, text: str, user_id: int):
    """Handle incoming text messages."""
    if not is_authorized(user_id):
        await bot.send_message(chat_id=chat_id, text="Unauthorized. This bot is private.")
        return

    raw_message = text
    logger.info(f"Processing message: {raw_message[:50]}...")

    # Clean up expired edit states
    clean_expired_edit_states()

    # Check if user is in edit state (responding to title/description prompt)
    if user_id in EDIT_STATE:
        state = EDIT_STATE[user_id]
        action = state.get("action")
        table = state.get("table")
        item_id = state.get("item_id")

        # Clear state immediately
        del EDIT_STATE[user_id]

        if action == "edit_title":
            result = update_item_title(table, item_id, raw_message.strip(), user_id)
            if result:
                item_title = result.get('name') or result.get('title', 'Item')
                text_msg, keyboard = build_bucket_list(table, f"\u270F\uFE0F *{item_title}*\nTitle updated!", user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text_msg, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.send_message(chat_id=chat_id, text="Failed to update title. Please try again.")
            return

        elif action == "edit_desc":
            result = update_item_description(table, item_id, raw_message.strip(), user_id)
            if result:
                item_title = result.get('name') or result.get('title', 'Item')
                text_msg, keyboard = build_bucket_list(table, f"\U0001F4DD *{item_title}*\nDescription updated!", user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text_msg, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.send_message(chat_id=chat_id, text="Failed to update description. Please try again.")
            return

    # Check for "done:" prefix
    if raw_message.lower().startswith("done:"):
        search_term = raw_message[5:].strip()
        if search_term:
            task = find_task_by_title(search_term, user_id)
            if task:
                result = mark_task_done(task["table"], task["id"], user_id)
                success = result.get("success", False) if isinstance(result, dict) else result
                next_occ = result.get("next_occurrence") if isinstance(result, dict) else None
                if success:
                    msg = f"Marked done: *{task['title']}*"
                    if next_occ:
                        msg += f"\n\n\U0001F504 _Recurring: Next due {next_occ['date']}_"
                    await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                else:
                    await bot.send_message(chat_id=chat_id, text="Failed to mark task done.")
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Couldn't find a task matching \"{search_term}\".\nTry /tasks to see all pending tasks."
                )
        else:
            await bot.send_message(chat_id=chat_id, text="Usage: `done: task name`", parse_mode="Markdown")
        return

    # Check for natural language deletion intent
    deletion_check = detect_deletion_intent(raw_message)
    logger.info(f"Deletion check result: {deletion_check}")
    if deletion_check.get("is_deletion") and deletion_check.get("task_hint"):
        search_term = deletion_check["task_hint"]
        table_hint = deletion_check.get("table_hint")
        item = find_item_for_deletion(search_term, user_id, table_hint)
        logger.info(f"Found item for deletion '{search_term}' (table hint: {table_hint}): {item}")
        if item:
            # Ask for confirmation before deleting
            confirm_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        text="\u2705 Yes, delete",
                        callback_data=f"confirm_del:{item['table']}:{item['id']}"
                    ),
                    InlineKeyboardButton(
                        text="\u274C No, keep it",
                        callback_data="cancel_del"
                    )
                ]
            ])
            await bot.send_message(
                chat_id=chat_id,
                text=f"Found *{item['title']}* in {item['table']}.\n\nDelete it?",
                reply_markup=confirm_keyboard,
                parse_mode="Markdown"
            )
            return
        else:
            # No match found - let it fall through to regular capture
            logger.info(f"No item found for deletion search: {search_term}")

    # Check for status change intent (pause, resume, etc.)
    status_check = detect_status_change_intent(raw_message)
    logger.info(f"Status change check result: {status_check}")
    if status_check.get("is_status_change") and status_check.get("task_hint") and status_check.get("new_status"):
        search_term = status_check["task_hint"]
        new_status = status_check["new_status"]
        table_hint = status_check.get("table_hint")
        item = find_item_for_status_change(search_term, user_id, table_hint)
        logger.info(f"Found item for status change '{search_term}': {item}")
        if item:
            updated = update_item_status(item["table"], item["id"], new_status, user_id)
            if updated:
                emoji = CATEGORY_EMOJI.get(item["table"], "")
                status_emoji = STATUS_EMOJI.get(item["table"], {}).get(new_status, "")
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"{emoji} Updated *{item['title']}* to {status_emoji} {new_status}",
                    parse_mode="Markdown"
                )
                return
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Failed to update status for '{item['title']}'."
                )
                return
        else:
            # No match found - let it fall through to regular capture
            logger.info(f"No item found for status change: {search_term}")

    # Check for natural language completion intent
    completion_check = detect_completion_intent(raw_message)
    logger.info(f"Completion check result: {completion_check}")
    if completion_check.get("is_completion") and completion_check.get("task_hint"):
        search_term = completion_check["task_hint"]
        task = find_task_by_title(search_term, user_id)
        logger.info(f"Found task for '{search_term}': {task}")
        if task:
            logger.info(f"Calling mark_task_done with table={task['table']}, id={task['id']}")
            result = mark_task_done(task["table"], task["id"], user_id)
            success = result.get("success", False) if isinstance(result, dict) else result
            next_occ = result.get("next_occurrence") if isinstance(result, dict) else None
            logger.info(f"mark_task_done returned: success={success}")
            if success:
                msg = f"Marked done: *{task['title']}*\n\n_(Detected from: \"{raw_message}\")_"
                if next_occ:
                    msg += f"\n\n\U0001F504 _Recurring: Next due {next_occ['date']}_"
                await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                return
            else:
                logger.error(f"mark_task_done returned False for task: {task}")
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Found task '{task['title']}' but failed to mark it done. Please try the button instead.",
                )
                return

    try:
        # Classify the message
        classification = classify_message(raw_message)
        category = classification.get("category", "needs_review")
        confidence = classification.get("confidence", 0.0)
        title = classification.get("title", "Untitled")

        logger.info(f"Classified as {category} ({confidence:.0%}): {title}")

        # Log to inbox
        inbox_record = log_to_inbox(raw_message, "telegram", classification, user_id)
        inbox_log_id = inbox_record.get("id") if inbox_record else None

        # Route to category table
        if inbox_log_id:
            target_table, target_record = route_to_category(classification, inbox_log_id, user_id)
            if target_record:
                update_inbox_log_processed(inbox_log_id, target_table, target_record.get("id"))

        # Send confirmation with fix buttons
        emoji = CATEGORY_EMOJI.get(category, "\U00002753")

        if category == "needs_review":
            reply = (
                f"{emoji} Captured for review\n\n"
                f"Title: {title}\n"
                f"Confidence: {confidence:.0%}\n\n"
                "I wasn't sure how to classify this. Tap a button to assign a category:"
            )
            keyboard = InlineKeyboardMarkup(build_fix_keyboard(inbox_log_id, category)) if inbox_log_id else None
        else:
            reply = (
                f"{emoji} Captured to {category}!\n\n"
                f"Title: {title}\n"
                f"Confidence: {confidence:.0%}"
            )

            if category == "projects" and classification.get("next_action"):
                reply += f"\nNext: {classification.get('next_action')}"
            if classification.get("due_date"):
                reply += f"\nDue: {classification.get('due_date')}"

            reply += "\n\nWrong category? Tap to fix:"
            keyboard = InlineKeyboardMarkup(build_fix_keyboard(inbox_log_id, category)) if inbox_log_id else None

        await bot.send_message(chat_id=chat_id, text=reply, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text="Sorry, something went wrong processing your message. Please try again."
        )


async def handle_callback(bot: Bot, callback_query_id: str, chat_id: int, message_id: int, user_id: int, data: str, message_text: str):
    """Handle callback queries (button presses)."""
    logger.info(f"Callback received: data={data}, user={user_id}, chat={chat_id}")

    if not is_authorized(user_id):
        logger.warning(f"Unauthorized callback from user {user_id}")
        return

    elif data == "noop":
        await bot.answer_callback_query(callback_query_id)

    elif data.startswith("fix:"):
        parts = data.split(":")
        if len(parts) != 3:
            return

        _, inbox_log_id, new_category = parts

        try:
            result = reclassify_item(inbox_log_id, new_category, user_id)
            if result:
                emoji = CATEGORY_EMOJI.get(new_category, "")
                new_text = (
                    f"{emoji} Moved to {new_category}!\n\n"
                    f"Title: {result.get('ai_title', 'Unknown')}\n"
                    f"(Manually reclassified)"
                )
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_text)

                # Show next item for review
                next_item = get_first_needs_review(user_id)
                if next_item:
                    text = (
                        f"*Next item to review:*\n\n"
                        f"*Title:* {next_item.get('ai_title', 'Unknown')}\n"
                        f"*Message:* {next_item.get('raw_message', '')[:200]}\n\n"
                        f"Tap a category:"
                    )
                    keyboard = InlineKeyboardMarkup(build_fix_keyboard(next_item["id"], "needs_review"))
                    await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error reclassifying: {e}")

    elif data.startswith("done:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id, text="Invalid data")
            return

        _, table, task_id = parts
        logger.info(f"COMPLETE: table={table}, id={task_id}")

        # Get item before marking done (for undo and title)
        item = get_item_by_id(table, task_id, user_id)
        item_title = item.get('name') or item.get('title', 'Item') if item else 'Item'

        # Save undo state before completing
        if item:
            save_undo_state(user_id, "complete", table, task_id, item)

        try:
            result = mark_task_done(table, task_id, user_id)
            # Handle both dict return (new) and legacy bool
            success = result.get("success", False) if isinstance(result, dict) else result
            next_occurrence = result.get("next_occurrence") if isinstance(result, dict) else None

            logger.info(f"COMPLETE: mark_task_done returned success={success}, next={next_occurrence}")

            if success:
                # Build completion message
                if next_occurrence:
                    action_msg = (
                        f"\u2705 *{item_title}*\n"
                        f"Marked complete!\n\n"
                        f"\U0001F504 _Recurring: Next due {next_occurrence['date']}_"
                    )
                else:
                    action_msg = f"\u2705 *{item_title}*\nMarked complete!"

                try:
                    text, keyboard = build_bucket_list(table, action_msg, user_id=user_id)
                    logger.info(f"COMPLETE: bucket list has {len(keyboard.inline_keyboard) if keyboard else 0} items")
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
                except Exception as e:
                    if "not modified" in str(e).lower():
                        logger.info(f"COMPLETE: Message not modified (same content)")
                        callback_text = f"✅ {item_title} done!"
                        if next_occurrence:
                            callback_text += f" Next: {next_occurrence['date']}"
                        await bot.answer_callback_query(callback_query_id, text=callback_text)
                    else:
                        logger.error(f"Error editing message: {e}")
                        await bot.answer_callback_query(callback_query_id, text=f"✅ {item_title} done!")
            else:
                logger.warning(f"COMPLETE: mark_task_done returned False for {table}:{task_id}")
                await bot.answer_callback_query(callback_query_id, text="Failed to complete")
        except Exception as e:
            logger.error(f"Error marking done: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("priority:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts

        try:
            # Get item before changing for undo
            item_before = get_item_by_id(table, item_id, user_id)
            if item_before:
                save_undo_state(user_id, "priority", table, item_id, item_before)

            result = toggle_item_priority(table, item_id, user_id)
            if result:
                new_priority = result.get("priority", "normal")
                priority_text = "high priority" if new_priority == "high" else "normal priority"
                emoji = "\u26A1" if new_priority == "high" else ""
                item = get_item_by_id(table, item_id, user_id)
                item_title = item.get('name') or item.get('title', 'Item') if item else 'Item'

                # Delete edit menu and send fresh list
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                text, keyboard = build_bucket_list(table, f"{emoji} *{item_title}*\nSet to {priority_text}!", user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to update priority")
        except Exception as e:
            logger.error(f"Error toggling priority: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("date:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts

        # Get item title for display
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Unknown') if item else 'Unknown'
        date_field = "follow_up_date" if table == "people" else "due_date"
        current_date = item.get(date_field) if item else None

        # Build date options keyboard
        today = date.today()
        keyboard = [
            [
                InlineKeyboardButton(text="Today", callback_data=f"setdate:{table}:{item_id}:today"),
                InlineKeyboardButton(text="Tomorrow", callback_data=f"setdate:{table}:{item_id}:tomorrow"),
            ],
            [
                InlineKeyboardButton(text="+3 days", callback_data=f"setdate:{table}:{item_id}:+3"),
                InlineKeyboardButton(text="+1 week", callback_data=f"setdate:{table}:{item_id}:+7"),
            ],
            [
                InlineKeyboardButton(text="\U0001F4C5 Pick date", callback_data=f"cal:{table}:{item_id}:{today.year}:{today.month}:show"),
            ],
            [
                InlineKeyboardButton(text="\U0001F5D1 Clear", callback_data=f"setdate:{table}:{item_id}:clear"),
                InlineKeyboardButton(text="\u274C Cancel", callback_data=f"cancel_edit:{table}"),
            ]
        ]

        current_str = f"\nCurrent: _{current_date}_" if current_date else ""
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"*{item_title}*\nSet {'follow-up' if table == 'people' else 'due'} date:{current_str}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error showing date options: {e}")

    elif data.startswith("setdate:"):
        parts = data.split(":")
        if len(parts) != 4:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id, date_option = parts

        # Get item before changing (for undo and title)
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Item') if item else 'Item'

        # Save undo state
        if item:
            save_undo_state(user_id, "date", table, item_id, item)

        # Calculate the actual date
        from datetime import timedelta
        if date_option == "today":
            new_date = date.today().isoformat()
        elif date_option == "tomorrow":
            new_date = (date.today() + timedelta(days=1)).isoformat()
        elif date_option == "+3":
            new_date = (date.today() + timedelta(days=3)).isoformat()
        elif date_option == "+7":
            new_date = (date.today() + timedelta(days=7)).isoformat()
        elif date_option == "clear":
            new_date = None
        else:
            new_date = None

        try:
            result = update_item_date(table, item_id, new_date, user_id)
            if result:
                date_msg = f"*{item_title}*\nDate set to {new_date}" if new_date else f"*{item_title}*\nDate cleared"
                # Delete date picker and send fresh list
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                text, keyboard = build_bucket_list(table, f"\U0001F4C5 {date_msg}!", user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to update date")
        except Exception as e:
            logger.error(f"Error setting date: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("cal:"):
        parts = data.split(":")
        if len(parts) != 6:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id, year_str, month_str, action = parts
        year, month = int(year_str), int(month_str)

        # Handle navigation
        if action == "prev":
            month -= 1
            if month < 1:
                month = 12
                year -= 1
        elif action == "next":
            month += 1
            if month > 12:
                month = 1
                year += 1

        # Get item title
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Unknown') if item else 'Unknown'

        keyboard = build_calendar_keyboard(table, item_id, year, month)

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"*{item_title}*\nSelect a date:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                logger.error(f"Error showing calendar: {e}")

    elif data.startswith("pickdate:"):
        parts = data.split(":")
        if len(parts) != 4:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id, date_str = parts

        # Get item before changing (for undo and title)
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Item') if item else 'Item'

        # Save undo state
        if item:
            save_undo_state(user_id, "date", table, item_id, item)

        try:
            result = update_item_date(table, item_id, date_str, user_id)
            if result:
                date_msg = f"*{item_title}*\nDate set to {date_str}"
                # Delete date picker and send fresh list
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                text, keyboard = build_bucket_list(table, f"\U0001F4C5 {date_msg}!", user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to set date")
        except Exception as e:
            logger.error(f"Error picking date: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("setsomeday:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts

        # Get item before changing (for undo and title)
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Item') if item else 'Item'

        # Save undo state
        if item:
            save_undo_state(user_id, "status", table, item_id, item)

        try:
            result = update_item_status(table, item_id, "someday", user_id)
            if result:
                # Delete edit menu and send fresh list
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                text, keyboard = build_bucket_list(table, f"\U0001F4AD *{item_title}*\nMoved to someday!", user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to update")
        except Exception as e:
            logger.error(f"Error setting someday: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("setpause:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts

        # Get item before changing (for undo and title)
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Item') if item else 'Item'

        # Save undo state
        if item:
            save_undo_state(user_id, "status", table, item_id, item)

        try:
            result = update_item_status(table, item_id, "paused", user_id)
            if result:
                # Delete edit menu and send fresh list
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                text, keyboard = build_bucket_list(table, f"\u23F8 *{item_title}*\nProject paused!", user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to pause")
        except Exception as e:
            logger.error(f"Error pausing: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("setactive:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts

        # Get item before changing (for undo and title)
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Item') if item else 'Item'

        # Save undo state
        if item:
            save_undo_state(user_id, "status", table, item_id, item)

        try:
            result = update_item_status(table, item_id, "active", user_id)
            if result:
                # Delete edit menu and send fresh list
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                text, keyboard = build_bucket_list(table, f"\U0001F7E2 *{item_title}*\nSet to active!", user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to set active")
        except Exception as e:
            logger.error(f"Error setting active: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("cancel:"):
        parts = data.split(":")
        if len(parts) != 2:
            return

        _, inbox_log_id = parts

        try:
            success = delete_item(inbox_log_id, user_id)
            if success:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="\u274C Cancelled and deleted."
                )
            else:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="Failed to delete. It may have already been removed."
                )
        except Exception as e:
            logger.error(f"Error cancelling item: {e}")

    elif data.startswith("delete:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, task_id = parts

        # Get item before deleting (for undo and title)
        item = get_item_by_id(table, task_id, user_id)
        item_title = item.get('name') or item.get('title', 'Item') if item else 'Item'

        # Save undo state before deleting
        if item:
            save_undo_state(user_id, "delete", table, task_id, item)

        try:
            success = delete_task(table, task_id, user_id)
            if success:
                try:
                    text, keyboard = build_bucket_list(table, f"\U0001F5D1 *{item_title}*\nDeleted!", user_id=user_id)
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
                except Exception as e:
                    if "not modified" in str(e).lower():
                        await bot.answer_callback_query(callback_query_id, text=f"🗑 {item_title} deleted")
                    else:
                        logger.error(f"Error editing message: {e}")
                        await bot.answer_callback_query(callback_query_id, text=f"🗑 {item_title} deleted")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to delete")
        except Exception as e:
            logger.error(f"Error deleting task: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("confirm_del:"):
        parts = data.split(":")
        if len(parts) != 3:
            return

        _, table, task_id = parts

        try:
            success = delete_task(table, task_id, user_id)
            if success:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="\U0001F5D1 Deleted!"
                )
            else:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="Failed to delete. It may have already been removed."
                )
        except Exception as e:
            logger.error(f"Error confirming delete: {e}")

    elif data == "cancel_del":
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Okay, kept it."
            )
        except Exception as e:
            logger.error(f"Error cancelling delete: {e}")

    elif data.startswith("edit:"):
        parts = data.split(":")
        if len(parts) != 3:
            return

        _, source_table, item_id = parts

        # Get item details to show title and check status
        item = get_item_by_id(source_table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Unknown') if item else 'Unknown'
        item_status = item.get('status', 'active') if item else 'active'
        is_recurring = item.get('is_recurring', False) if item else False

        # Build Edit menu - organized into clear sections
        keyboard = []

        # --- Section: Edit fields ---
        keyboard.append([
            InlineKeyboardButton(text="\u2500\u2500 Edit \u2500\u2500", callback_data="noop"),
        ])
        keyboard.append([
            InlineKeyboardButton(text="\u270F\uFE0F Title", callback_data=f"edit_title:{source_table}:{item_id}"),
            InlineKeyboardButton(text="\U0001F4DD Description", callback_data=f"edit_desc:{source_table}:{item_id}"),
        ])

        # --- Section: Properties ---
        keyboard.append([
            InlineKeyboardButton(text="\u2500\u2500 Properties \u2500\u2500", callback_data="noop"),
        ])
        item_priority = item.get('priority', 'normal') if item else 'normal'
        priority_label = "\u26A1 Priority: HIGH" if item_priority == "high" else "\u25CB Priority: normal"
        props_row = [
            InlineKeyboardButton(text=priority_label, callback_data=f"priority:{source_table}:{item_id}"),
        ]
        if source_table != "ideas":
            props_row.append(InlineKeyboardButton(text="\U0001F4C5 Date", callback_data=f"date:{source_table}:{item_id}"))
        keyboard.append(props_row)

        # Recurrence option (not for ideas)
        if source_table != "ideas":
            recur_text = "\U0001F504 Recurrence" if not is_recurring else "\U0001F504 Recurrence \u2705"
            keyboard.append([InlineKeyboardButton(text=recur_text, callback_data=f"recur:{source_table}:{item_id}")])

        # --- Section: Move / Status ---
        keyboard.append([
            InlineKeyboardButton(text="\u2500\u2500 Move / Status \u2500\u2500", callback_data="noop"),
        ])

        # Bucket move options (excluding current table)
        options = []
        for cat in CATEGORIES:
            if cat != source_table:
                emoji = CATEGORY_EMOJI.get(cat, "")
                options.append(InlineKeyboardButton(
                    text=f"{emoji} {cat}",
                    callback_data=f"moveto:{source_table}:{item_id}:{cat}"
                ))
        keyboard.append(options[:2])
        keyboard.append(options[2:])

        # Status change options
        status_row = []
        if item_status in ['someday', 'paused']:
            status_row.append(InlineKeyboardButton(
                text="\U0001F7E2 active",
                callback_data=f"setactive:{source_table}:{item_id}"
            ))
        status_row.append(InlineKeyboardButton(
            text="\U0001F4AD someday",
            callback_data=f"setsomeday:{source_table}:{item_id}"
        ))
        if source_table == "projects" and item_status == "active":
            status_row.append(InlineKeyboardButton(
                text="\u23F8 pause",
                callback_data=f"setpause:{source_table}:{item_id}"
            ))
        keyboard.append(status_row)

        # Cancel button - includes table so we can re-render the list
        keyboard.append([InlineKeyboardButton(text="\u274C Cancel", callback_data=f"cancel_edit:{source_table}")])

        try:
            # Send edit menu as a NEW message (keeps list visible)
            await bot.send_message(
                chat_id=chat_id,
                text=f"*{item_title}*\nEdit or move:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error showing edit/move options: {e}")

    elif data.startswith("edit_title:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts

        # Get item title for prompt
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Unknown') if item else 'Unknown'

        # Set edit state for this user
        from datetime import datetime
        EDIT_STATE[user_id] = {
            "action": "edit_title",
            "table": table,
            "item_id": item_id,
            "timestamp": datetime.utcnow()
        }

        # Send prompt with ForceReply
        from telegram import ForceReply
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"Enter new title for *{item_title}*:",
                parse_mode="Markdown",
                reply_markup=ForceReply(selective=True, input_field_placeholder="New title...")
            )
            # Delete the menu message
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.error(f"Error prompting for title: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("edit_desc:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts

        # Get item title for prompt
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Unknown') if item else 'Unknown'

        # Set edit state for this user
        from datetime import datetime
        EDIT_STATE[user_id] = {
            "action": "edit_desc",
            "table": table,
            "item_id": item_id,
            "timestamp": datetime.utcnow()
        }

        # Send prompt with ForceReply
        from telegram import ForceReply
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"Enter new description for *{item_title}*:",
                parse_mode="Markdown",
                reply_markup=ForceReply(selective=True, input_field_placeholder="New description...")
            )
            # Delete the menu message
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.error(f"Error prompting for description: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("recur:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts

        # Get item for display
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Unknown') if item else 'Unknown'
        current_pattern = item.get('recurrence_pattern') if item else None
        is_recurring = item.get('is_recurring', False) if item else False

        # Build recurrence picker
        keyboard = [
            [InlineKeyboardButton(text="\U0001F4C5 Daily", callback_data=f"setrec:{table}:{item_id}:daily")],
            [
                InlineKeyboardButton(text="Mon", callback_data=f"setrec:{table}:{item_id}:weekly:0"),
                InlineKeyboardButton(text="Tue", callback_data=f"setrec:{table}:{item_id}:weekly:1"),
                InlineKeyboardButton(text="Wed", callback_data=f"setrec:{table}:{item_id}:weekly:2"),
                InlineKeyboardButton(text="Thu", callback_data=f"setrec:{table}:{item_id}:weekly:3"),
            ],
            [
                InlineKeyboardButton(text="Fri", callback_data=f"setrec:{table}:{item_id}:weekly:4"),
                InlineKeyboardButton(text="Sat", callback_data=f"setrec:{table}:{item_id}:weekly:5"),
                InlineKeyboardButton(text="Sun", callback_data=f"setrec:{table}:{item_id}:weekly:6"),
            ],
            [InlineKeyboardButton(text="\U0001F4C6 Monthly (same date)", callback_data=f"setrec:{table}:{item_id}:monthly_date")],
            [InlineKeyboardButton(text="\U0001F5D3 Biweekly...", callback_data=f"recurbi:{table}:{item_id}")],
            [InlineKeyboardButton(text="\U0001F5D3 Monthly (1st Mon, etc)...", callback_data=f"recurmo:{table}:{item_id}")],
        ]

        # Add clear option if currently recurring
        if is_recurring:
            keyboard.append([InlineKeyboardButton(text="\u274C Clear recurrence", callback_data=f"clearrec:{table}:{item_id}")])

        keyboard.append([InlineKeyboardButton(text="\u2B05 Back", callback_data=f"move:{table}:{item_id}")])

        current_str = f"\nCurrent: _{current_pattern}_" if current_pattern else ""

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"*{item_title}*\nSet recurrence:{current_str}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error showing recurrence picker: {e}")

    elif data.startswith("recurbi:"):
        # Biweekly submenu
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Unknown') if item else 'Unknown'

        keyboard = [
            [
                InlineKeyboardButton(text="Mon", callback_data=f"setrec:{table}:{item_id}:biweekly:0"),
                InlineKeyboardButton(text="Tue", callback_data=f"setrec:{table}:{item_id}:biweekly:1"),
                InlineKeyboardButton(text="Wed", callback_data=f"setrec:{table}:{item_id}:biweekly:2"),
                InlineKeyboardButton(text="Thu", callback_data=f"setrec:{table}:{item_id}:biweekly:3"),
            ],
            [
                InlineKeyboardButton(text="Fri", callback_data=f"setrec:{table}:{item_id}:biweekly:4"),
                InlineKeyboardButton(text="Sat", callback_data=f"setrec:{table}:{item_id}:biweekly:5"),
                InlineKeyboardButton(text="Sun", callback_data=f"setrec:{table}:{item_id}:biweekly:6"),
            ],
            [InlineKeyboardButton(text="\u2B05 Back", callback_data=f"recur:{table}:{item_id}")],
        ]

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"*{item_title}*\nBiweekly on which day?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error showing biweekly picker: {e}")

    elif data.startswith("recurmo:"):
        # Monthly weekday submenu (first Monday, etc.)
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Unknown') if item else 'Unknown'

        keyboard = [
            [
                InlineKeyboardButton(text="1st Mon", callback_data=f"setrec:{table}:{item_id}:monthly:first_mon"),
                InlineKeyboardButton(text="1st Tue", callback_data=f"setrec:{table}:{item_id}:monthly:first_tue"),
            ],
            [
                InlineKeyboardButton(text="1st Wed", callback_data=f"setrec:{table}:{item_id}:monthly:first_wed"),
                InlineKeyboardButton(text="1st Thu", callback_data=f"setrec:{table}:{item_id}:monthly:first_thu"),
            ],
            [
                InlineKeyboardButton(text="1st Fri", callback_data=f"setrec:{table}:{item_id}:monthly:first_fri"),
                InlineKeyboardButton(text="Last day", callback_data=f"setrec:{table}:{item_id}:monthly:last"),
            ],
            [InlineKeyboardButton(text="\u2B05 Back", callback_data=f"recur:{table}:{item_id}")],
        ]

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"*{item_title}*\nMonthly on which pattern?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error showing monthly picker: {e}")

    elif data.startswith("setrec:"):
        parts = data.split(":")
        if len(parts) < 4:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts[:3]
        pattern_parts = parts[3:]

        # Get item for display
        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Unknown') if item else 'Unknown'

        # Construct pattern string
        if pattern_parts[0] == "monthly_date":
            # Monthly on same date - get current due date
            date_field = "follow_up_date" if table == "people" else "due_date"
            current_date = item.get(date_field) if item else None
            if current_date:
                from datetime import datetime
                day = datetime.strptime(current_date, "%Y-%m-%d").day
                pattern = f"monthly:{day}"
            else:
                # Default to 1st of month if no date set
                pattern = "monthly:1"
        elif len(pattern_parts) == 1:
            pattern = pattern_parts[0]  # daily, monthly:last, monthly:first_mon, etc.
        else:
            pattern = ":".join(pattern_parts)  # weekly:0, biweekly:4, etc.

        try:
            result = set_recurrence_pattern(table, item_id, pattern, user_id)
            if result:
                # Calculate next occurrence for display
                next_date = calculate_next_occurrence(pattern)
                # Delete recurrence menu and send fresh list
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                text_msg, keyboard = build_bucket_list(
                    table,
                    f"\U0001F504 *{item_title}*\nRecurrence set: {pattern}\nNext: {next_date}",
                    user_id=user_id
                )
                await bot.send_message(chat_id=chat_id, text=text_msg, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to set recurrence")
        except Exception as e:
            logger.error(f"Error setting recurrence: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("clearrec:"):
        parts = data.split(":")
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query_id)
            return

        _, table, item_id = parts

        item = get_item_by_id(table, item_id, user_id)
        item_title = item.get('name') or item.get('title', 'Unknown') if item else 'Unknown'

        try:
            result = clear_recurrence(table, item_id, user_id)
            if result:
                # Delete recurrence menu and send fresh list
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                text_msg, keyboard = build_bucket_list(table, f"\U0001F504 *{item_title}*\nRecurrence cleared!", user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text_msg, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to clear recurrence")
        except Exception as e:
            logger.error(f"Error clearing recurrence: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("moveto:"):
        parts = data.split(":")
        if len(parts) != 4:
            await bot.answer_callback_query(callback_query_id)
            return

        _, source_table, item_id, dest_table = parts

        # Get item before moving (for undo - note: move undo is limited)
        item_before = get_item_by_id(source_table, item_id, user_id)
        if item_before:
            item_before['_source_table'] = source_table  # Store source for potential undo
            save_undo_state(user_id, "move", source_table, item_id, item_before)

        try:
            result = move_item(source_table, item_id, dest_table, user_id)
            if result:
                emoji = CATEGORY_EMOJI.get(dest_table, "")
                action_msg = f"{emoji} Moved {result['title']} to {dest_table}!"
                # Delete edit menu and send fresh list
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                text, keyboard = build_bucket_list(source_table, action_msg, user_id=user_id)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to move")
        except Exception as e:
            logger.error(f"Error moving item: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("cancel_edit:"):
        parts = data.split(":")
        table = parts[1] if len(parts) == 2 else None

        try:
            # Delete the edit menu message
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.error(f"Error deleting edit menu: {e}")

    elif data == "cancel_move":
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Cancelled."
            )
        except Exception as e:
            logger.error(f"Error cancelling: {e}")

    elif data.startswith("undo:"):
        parts = data.split(":")
        bucket = parts[1] if len(parts) == 2 else None

        try:
            result = execute_undo(user_id)
            if result["success"]:
                # Use the table from undo result if available, otherwise use bucket from callback
                table = result.get("table", bucket)
                text, keyboard = build_bucket_list(table, f"\u21A9\uFE0F {result['message']}", user_id=user_id)
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text=result["message"])
        except Exception as e:
            logger.error(f"Error executing undo: {e}")
            await bot.answer_callback_query(callback_query_id, text="Undo failed")

    await bot.answer_callback_query(callback_query_id)


async def process_update(update_data: dict):
    """Process a Telegram update."""
    validate_config()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    update = Update.de_json(update_data, bot)

    if update.message:
        chat_id = update.message.chat_id
        user_id = update.effective_user.id

        if update.message.text:
            text = update.message.text

            if text.startswith("/"):
                command = text.split()[0]
                # /myid works for anyone (even unauthorized)
                if command == "/myid":
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"Your Telegram ID: `{user_id}`\n\n_Send this to the bot admin to get access._",
                        parse_mode="Markdown"
                    )
                # Handle /settings specially since it needs full text for arguments
                elif command == "/settings":
                    if is_authorized(user_id):
                        await handle_settings_command(bot, chat_id, text, user_id)
                    else:
                        await bot.send_message(chat_id=chat_id, text="Unauthorized. This bot is private.")
                # Admin commands that need full text
                elif command in ["/invite", "/remove"]:
                    if is_authorized(user_id):
                        await handle_admin_command(bot, chat_id, text, user_id)
                    else:
                        await bot.send_message(chat_id=chat_id, text="Unauthorized. This bot is private.")
                else:
                    await handle_command(bot, chat_id, command, user_id)
            else:
                await handle_message(bot, chat_id, text, user_id)

        elif update.message.voice:
            await bot.send_message(
                chat_id=chat_id,
                text="Voice messages received! Voice transcription coming soon. Please send text for now."
            )

    elif update.callback_query:
        logger.info(f"Processing callback_query: {update.callback_query.data}")
        chat_id = update.callback_query.message.chat_id
        message_id = update.callback_query.message.message_id
        user_id = update.callback_query.from_user.id
        data = update.callback_query.data
        message_text = update.callback_query.message.text or ""
        callback_id = update.callback_query.id

        await handle_callback(bot, callback_id, chat_id, message_id, user_id, data, message_text)
    else:
        logger.info(f"Unhandled update type: {update_data.keys()}")


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler."""

    def do_POST(self):
        """Handle POST requests from Telegram webhook."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            update_data = json.loads(body.decode('utf-8'))

            logger.info(f"Received update: {update_data.get('update_id')}, keys: {list(update_data.keys())}")

            # Process the update
            import asyncio
            asyncio.run(process_update(update_data))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())

        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "Second Brain webhook active"}).encode())
