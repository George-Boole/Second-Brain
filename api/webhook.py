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

from config import TELEGRAM_BOT_TOKEN, ALLOWED_USER_IDS, validate_config
from classifier import classify_message, detect_completion_intent, detect_deletion_intent
from database import (
    log_to_inbox, route_to_category, update_inbox_log_processed, reclassify_item,
    get_first_needs_review, mark_task_done, find_task_by_title,
    delete_item, delete_task, find_item_for_deletion, get_all_active_items, move_item,
    get_setting, set_setting, get_all_settings
)
from scheduler import generate_digest, generate_evening_recap

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

# Status emoji mapping for list view
STATUS_EMOJI = {
    "admin": {"pending": "\u26AA", "in_progress": "\U0001F7E1"},  # white/yellow circle
    "projects": {"active": "\U0001F7E2", "paused": "\u23F8"},     # green circle/pause
    "ideas": {"captured": "\U0001F4A1", "exploring": "\U0001F50D", "actionable": "\U0001F3AF"},
}

CATEGORIES = ["people", "projects", "ideas", "admin"]


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


def build_bucket_list(bucket: str, action_msg: str = None, all_items: dict = None) -> tuple:
    """
    Build text and keyboard for a bucket list.
    Returns (text, keyboard) tuple.
    """
    items = all_items if all_items is not None else get_all_active_items()
    bucket_items = items.get(bucket, [])

    if not bucket_items:
        text = action_msg + "\n\n" if action_msg else ""
        text += f"_No more items in {bucket}._"
        return (text, None)

    emoji = CATEGORY_EMOJI.get(bucket, "")
    text = action_msg + "\n\n" if action_msg else ""
    text += f"*{emoji} {bucket.title()}:*\n"
    buttons = []

    for i, item in enumerate(bucket_items, 1):
        # Get title (people use 'name', others use 'title')
        title = item.get('name') or item.get('title', 'Untitled')
        status = item.get('status', '')

        # Get date and check if overdue
        date_field = item.get('due_date') if bucket in ['admin', 'projects'] else item.get('follow_up_date')
        formatted_date = format_date_relative(date_field) if date_field else None
        is_overdue = formatted_date == "overdue!"

        # Status emoji (red circle if overdue)
        status_emoji = "\U0001F534" if is_overdue else STATUS_EMOJI.get(bucket, {}).get(status, "")

        # Build line
        text += f"{i}. {status_emoji} {title}" if status_emoji else f"{i}. {title}"

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

        buttons.append([
            InlineKeyboardButton(text=f"{i}", callback_data="noop"),
            InlineKeyboardButton(text="\u2705", callback_data=f"done:{bucket}:{item['id']}"),
            InlineKeyboardButton(text=f"⇄ {title[:30]}", callback_data=f"move:{bucket}:{item['id']}"),
            InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delete:{bucket}:{item['id']}")
        ])

    keyboard = InlineKeyboardMarkup(buttons) if buttons else None
    return (text, keyboard)


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized."""
    return user_id in ALLOWED_USER_IDS


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
            "/start - Welcome message\n"
            "/help - This help text\n"
            "/list - View all active items\n"
            "/admin - Admin tasks\n"
            "/projects - Projects\n"
            "/people - People\n"
            "/ideas - Ideas\n"
            "/digest - Morning digest\n"
            "/recap - Evening recap\n"
            "/settings - Configure timezone & digest times\n"
            "/review - Classify needs\\_review items\n\n"
            "*Category Prefixes:*\n"
            "`person:` Force people category\n"
            "`project:` Force projects category\n"
            "`idea:` Force ideas category\n"
            "`admin:` Force admin category\n\n"
            "*Natural Language:*\n"
            "`done: task name` - Mark a task complete\n"
            "\"I called Sarah\" - Marks matching task done\n"
            "\"Remove X from projects\" - Deletes entry\n\n"
            "*Buttons:*\n"
            "\u274C Cancel - Delete a misclassified entry\n"
            "\u2705 Done - Mark task complete\n"
            "\U0001F5D1 Delete - Remove task entirely\n\n"
            "Just send any message to capture a thought!"
        )
        await bot.send_message(chat_id=chat_id, text=help_text, parse_mode="Markdown")

    elif command == "/digest":
        await bot.send_message(chat_id=chat_id, text="Generating your digest...")
        try:
            digest = generate_digest()
            await bot.send_message(chat_id=chat_id, text=digest, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error generating digest: {e}")
            await bot.send_message(chat_id=chat_id, text=f"Error generating digest: {str(e)}")

    elif command == "/review":
        item = get_first_needs_review()
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
        items = get_all_active_items()
        total = sum(len(v) for v in items.values())

        if total == 0:
            await bot.send_message(chat_id=chat_id, text="No active items in any bucket.")
            return

        # Send each bucket as a separate message
        for bucket in CATEGORIES:
            if items.get(bucket):
                text, keyboard = build_bucket_list(bucket, all_items=items)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

        await bot.send_message(chat_id=chat_id, text=f"_Total: {total} active items_", parse_mode="Markdown")

    elif command in ["/admin", "/projects", "/people", "/ideas"]:
        bucket = command[1:]
        text, keyboard = build_bucket_list(bucket)
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

    elif command == "/recap":
        await bot.send_message(chat_id=chat_id, text="Generating evening recap...")
        try:
            recap = generate_evening_recap()
            await bot.send_message(chat_id=chat_id, text=recap, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error generating recap: {e}")
            await bot.send_message(chat_id=chat_id, text=f"Error generating recap: {str(e)}")

    elif command == "/settings" or command.startswith("/settings "):
        # Handle settings command - need full text for arguments
        pass  # Will be handled in handle_message for full text access


async def handle_settings_command(bot: Bot, chat_id: int, text: str):
    """Handle /settings command with optional arguments."""
    parts = text.split(maxsplit=2)

    if len(parts) == 1:
        # Show current settings
        settings = get_all_settings()
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
            current = get_setting(setting_key)
            await bot.send_message(chat_id=chat_id, text=f"Current {parts[1]}: `{current}`\n\nUsage: `/settings {parts[1]} <value>`", parse_mode="Markdown")
        else:
            set_setting(setting_key, parts[2])
            await bot.send_message(chat_id=chat_id, text=f"\u2705 Updated {parts[1]} to `{parts[2]}`", parse_mode="Markdown")


async def handle_message(bot: Bot, chat_id: int, text: str, user_id: int):
    """Handle incoming text messages."""
    if not is_authorized(user_id):
        await bot.send_message(chat_id=chat_id, text="Unauthorized. This bot is private.")
        return

    raw_message = text
    logger.info(f"Processing message: {raw_message[:50]}...")

    # Check for "done:" prefix
    if raw_message.lower().startswith("done:"):
        search_term = raw_message[5:].strip()
        if search_term:
            task = find_task_by_title(search_term)
            if task:
                success = mark_task_done(task["table"], task["id"])
                if success:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"Marked done: *{task['title']}*",
                        parse_mode="Markdown"
                    )
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
        item = find_item_for_deletion(search_term, table_hint)
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

    # Check for natural language completion intent
    completion_check = detect_completion_intent(raw_message)
    logger.info(f"Completion check result: {completion_check}")
    if completion_check.get("is_completion") and completion_check.get("task_hint"):
        search_term = completion_check["task_hint"]
        task = find_task_by_title(search_term)
        logger.info(f"Found task for '{search_term}': {task}")
        if task:
            logger.info(f"Calling mark_task_done with table={task['table']}, id={task['id']}")
            success = mark_task_done(task["table"], task["id"])
            logger.info(f"mark_task_done returned: {success}")
            if success:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Marked done: *{task['title']}*\n\n_(Detected from: \"{raw_message}\")_",
                    parse_mode="Markdown"
                )
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
        inbox_record = log_to_inbox(raw_message, "telegram", classification)
        inbox_log_id = inbox_record.get("id") if inbox_record else None

        # Route to category table
        if inbox_log_id:
            target_table, target_record = route_to_category(classification, inbox_log_id)
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
            result = reclassify_item(inbox_log_id, new_category)
            if result:
                emoji = CATEGORY_EMOJI.get(new_category, "")
                new_text = (
                    f"{emoji} Moved to {new_category}!\n\n"
                    f"Title: {result.get('ai_title', 'Unknown')}\n"
                    f"(Manually reclassified)"
                )
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_text)

                # Show next item for review
                next_item = get_first_needs_review()
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

        try:
            success = mark_task_done(table, task_id)
            logger.info(f"COMPLETE: mark_task_done returned {success}")
            if success:
                try:
                    text, keyboard = build_bucket_list(table, "\u2705 Marked complete!")
                    logger.info(f"COMPLETE: bucket list has {len(keyboard.inline_keyboard) if keyboard else 0} items")
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
                except Exception as e:
                    if "not modified" in str(e).lower():
                        logger.info(f"COMPLETE: Message not modified (same content)")
                        await bot.answer_callback_query(callback_query_id, text="\u2705 Done!")
                    else:
                        logger.error(f"Error editing message: {e}")
                        await bot.answer_callback_query(callback_query_id, text="\u2705 Done!")
            else:
                logger.warning(f"COMPLETE: mark_task_done returned False for {table}:{task_id}")
                await bot.answer_callback_query(callback_query_id, text="Failed to complete")
        except Exception as e:
            logger.error(f"Error marking done: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data.startswith("cancel:"):
        parts = data.split(":")
        if len(parts) != 2:
            return

        _, inbox_log_id = parts

        try:
            success = delete_item(inbox_log_id)
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

        try:
            success = delete_task(table, task_id)
            if success:
                try:
                    text, keyboard = build_bucket_list(table, "\U0001F5D1 Deleted!")
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
                except Exception as e:
                    if "not modified" in str(e).lower():
                        await bot.answer_callback_query(callback_query_id, text="\U0001F5D1 Deleted!")
                    else:
                        logger.error(f"Error editing message: {e}")
                        await bot.answer_callback_query(callback_query_id, text="\U0001F5D1 Deleted!")
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
            success = delete_task(table, task_id)
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

    elif data.startswith("move:"):
        parts = data.split(":")
        if len(parts) != 3:
            return

        _, source_table, item_id = parts

        # Show destination options (excluding current table)
        dest_buttons = []
        for cat in CATEGORIES:
            if cat != source_table:
                emoji = CATEGORY_EMOJI.get(cat, "")
                dest_buttons.append(InlineKeyboardButton(
                    text=f"{emoji} {cat}",
                    callback_data=f"moveto:{source_table}:{item_id}:{cat}"
                ))
        # Arrange in 2x2 grid + cancel
        keyboard = [dest_buttons[:2], dest_buttons[2:], [
            InlineKeyboardButton(text="\u274C Cancel", callback_data="cancel_move")
        ]]

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"Move to which bucket?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing move options: {e}")

    elif data.startswith("moveto:"):
        parts = data.split(":")
        if len(parts) != 4:
            await bot.answer_callback_query(callback_query_id)
            return

        _, source_table, item_id, dest_table = parts

        try:
            result = move_item(source_table, item_id, dest_table)
            if result:
                emoji = CATEGORY_EMOJI.get(dest_table, "")
                action_msg = f"{emoji} Moved {result['title']} to {dest_table}!"
                try:
                    text, keyboard = build_bucket_list(source_table, action_msg)
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
                except Exception as e:
                    if "not modified" in str(e).lower():
                        await bot.answer_callback_query(callback_query_id, text=f"Moved to {dest_table}!")
                    else:
                        logger.error(f"Error editing message: {e}")
                        await bot.answer_callback_query(callback_query_id, text=f"Moved to {dest_table}!")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to move")
        except Exception as e:
            logger.error(f"Error moving item: {e}")
            await bot.answer_callback_query(callback_query_id, text="Error occurred")

    elif data == "cancel_move":
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Move cancelled."
            )
        except Exception as e:
            logger.error(f"Error cancelling move: {e}")

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
                # Handle /settings specially since it needs full text for arguments
                if command == "/settings":
                    if is_authorized(user_id):
                        await handle_settings_command(bot, chat_id, text)
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
