"""Vercel serverless function for Telegram webhook."""

import json
import logging
import sys
import os

# Add bot directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bot'))

from http.server import BaseHTTPRequestHandler
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup

from config import TELEGRAM_BOT_TOKEN, ALLOWED_USER_IDS, validate_config
from classifier import classify_message, detect_completion_intent, detect_deletion_intent
from database import (
    log_to_inbox, route_to_category, update_inbox_log_processed, reclassify_item,
    get_first_needs_review, mark_task_done, find_task_by_title,
    delete_item, delete_task, find_item_for_deletion, get_all_active_items, move_item
)
from scheduler import generate_digest

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

CATEGORIES = ["people", "projects", "ideas", "admin"]


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
            "/digest - Daily digest\n"
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
            "Just send any message to capture a thought!\n"
            "Daily digest at 7 AM Mountain Time."
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

        # Send each bucket as a separate message with complete/move/delete buttons
        if items["admin"]:
            text = "*\u2705 Admin Tasks:*\n"
            buttons = []
            for item in items["admin"]:
                text += f"• {item['title']}"
                if item.get('due_date'):
                    text += f" _(due: {item['due_date']})_"
                text += "\n"
                buttons.append([
                    InlineKeyboardButton(text="\u2705", callback_data=f"done:admin:{item['id']}"),
                    InlineKeyboardButton(text=f"\u21C4 {item['title'][:15]}", callback_data=f"move:admin:{item['id']}"),
                    InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delete:admin:{item['id']}")
                ])
            keyboard = InlineKeyboardMarkup(buttons) if buttons else None
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

        if items["projects"]:
            text = "*\U0001F4CB Projects:*\n"
            buttons = []
            for item in items["projects"]:
                text += f"• {item['title']}"
                if item.get('status') == 'paused':
                    text += " _(paused)_"
                if item.get('next_action'):
                    text += f"\n  ↳ Next: {item['next_action'][:50]}"
                text += "\n"
                buttons.append([
                    InlineKeyboardButton(text="\u2705", callback_data=f"done:projects:{item['id']}"),
                    InlineKeyboardButton(text=f"\u21C4 {item['title'][:15]}", callback_data=f"move:projects:{item['id']}"),
                    InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delete:projects:{item['id']}")
                ])
            keyboard = InlineKeyboardMarkup(buttons) if buttons else None
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

        if items["people"]:
            text = "*\U0001F464 People:*\n"
            buttons = []
            for item in items["people"]:
                text += f"• {item['name']}"
                if item.get('follow_up_date'):
                    text += f" _(follow up: {item['follow_up_date']})_"
                text += "\n"
                buttons.append([
                    InlineKeyboardButton(text="\u2705", callback_data=f"done:people:{item['id']}"),
                    InlineKeyboardButton(text=f"\u21C4 {item['name'][:15]}", callback_data=f"move:people:{item['id']}"),
                    InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delete:people:{item['id']}")
                ])
            keyboard = InlineKeyboardMarkup(buttons) if buttons else None
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

        if items["ideas"]:
            text = "*\U0001F4A1 Ideas:*\n"
            buttons = []
            for item in items["ideas"]:
                text += f"• {item['title']}\n"
                buttons.append([
                    InlineKeyboardButton(text="\u2705", callback_data=f"done:ideas:{item['id']}"),
                    InlineKeyboardButton(text=f"\u21C4 {item['title'][:15]}", callback_data=f"move:ideas:{item['id']}"),
                    InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delete:ideas:{item['id']}")
                ])
            keyboard = InlineKeyboardMarkup(buttons) if buttons else None
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

        await bot.send_message(chat_id=chat_id, text=f"_Total: {total} active items_", parse_mode="Markdown")

    elif command == "/admin":
        items = get_all_active_items()
        if not items["admin"]:
            await bot.send_message(chat_id=chat_id, text="No active admin tasks.")
            return

        text = "*\u2705 Admin Tasks:*\n"
        buttons = []
        for item in items["admin"]:
            text += f"• {item['title']}"
            if item.get('due_date'):
                text += f" _(due: {item['due_date']})_"
            text += "\n"
            buttons.append([
                InlineKeyboardButton(text="\u2705", callback_data=f"done:admin:{item['id']}"),
                InlineKeyboardButton(text=f"\u21C4 {item['title'][:15]}", callback_data=f"move:admin:{item['id']}"),
                InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delete:admin:{item['id']}")
            ])
        keyboard = InlineKeyboardMarkup(buttons) if buttons else None
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

    elif command == "/projects":
        items = get_all_active_items()
        if not items["projects"]:
            await bot.send_message(chat_id=chat_id, text="No active projects.")
            return

        text = "*\U0001F4CB Projects:*\n"
        buttons = []
        for item in items["projects"]:
            text += f"• {item['title']}"
            if item.get('status') == 'paused':
                text += " _(paused)_"
            if item.get('next_action'):
                text += f"\n  ↳ Next: {item['next_action'][:50]}"
            text += "\n"
            buttons.append([
                InlineKeyboardButton(text="\u2705", callback_data=f"done:projects:{item['id']}"),
                InlineKeyboardButton(text=f"\u21C4 {item['title'][:15]}", callback_data=f"move:projects:{item['id']}"),
                InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delete:projects:{item['id']}")
            ])
        keyboard = InlineKeyboardMarkup(buttons) if buttons else None
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

    elif command == "/people":
        items = get_all_active_items()
        if not items["people"]:
            await bot.send_message(chat_id=chat_id, text="No people entries.")
            return

        text = "*\U0001F464 People:*\n"
        buttons = []
        for item in items["people"]:
            text += f"• {item['name']}"
            if item.get('follow_up_date'):
                text += f" _(follow up: {item['follow_up_date']})_"
            text += "\n"
            buttons.append([
                InlineKeyboardButton(text="\u2705", callback_data=f"done:people:{item['id']}"),
                InlineKeyboardButton(text=f"\u21C4 {item['name'][:15]}", callback_data=f"move:people:{item['id']}"),
                InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delete:people:{item['id']}")
            ])
        keyboard = InlineKeyboardMarkup(buttons) if buttons else None
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

    elif command == "/ideas":
        items = get_all_active_items()
        if not items["ideas"]:
            await bot.send_message(chat_id=chat_id, text="No active ideas.")
            return

        text = "*\U0001F4A1 Ideas:*\n"
        buttons = []
        for item in items["ideas"]:
            text += f"• {item['title']}\n"
            buttons.append([
                InlineKeyboardButton(text="\u2705", callback_data=f"done:ideas:{item['id']}"),
                InlineKeyboardButton(text=f"\u21C4 {item['title'][:15]}", callback_data=f"move:ideas:{item['id']}"),
                InlineKeyboardButton(text="\U0001F5D1", callback_data=f"delete:ideas:{item['id']}")
            ])
        keyboard = InlineKeyboardMarkup(buttons) if buttons else None
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="Markdown")

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
    if not is_authorized(user_id):
        return

    if data.startswith("fix:"):
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
            return

        _, table, task_id = parts

        try:
            success = mark_task_done(table, task_id)
            if success:
                new_text = message_text + "\n\n_Marked complete!_"
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error marking done: {e}")

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
            return

        _, table, task_id = parts

        try:
            success = delete_task(table, task_id)
            if success:
                new_text = message_text + "\n\n_Deleted!_"
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_text, parse_mode="Markdown")
            else:
                await bot.answer_callback_query(callback_query_id, text="Failed to delete")
                return
        except Exception as e:
            logger.error(f"Error deleting task: {e}")

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
            return

        _, source_table, item_id, dest_table = parts

        try:
            result = move_item(source_table, item_id, dest_table)
            if result:
                emoji = CATEGORY_EMOJI.get(dest_table, "")
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"{emoji} Moved *{result['title']}* to {dest_table}!",
                    parse_mode="Markdown"
                )
            else:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="Failed to move item."
                )
        except Exception as e:
            logger.error(f"Error moving item: {e}")

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
                await handle_command(bot, chat_id, command, user_id)
            else:
                await handle_message(bot, chat_id, text, user_id)

        elif update.message.voice:
            await bot.send_message(
                chat_id=chat_id,
                text="Voice messages received! Voice transcription coming soon. Please send text for now."
            )

    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id
        message_id = update.callback_query.message.message_id
        user_id = update.callback_query.from_user.id
        data = update.callback_query.data
        message_text = update.callback_query.message.text or ""
        callback_id = update.callback_query.id

        await handle_callback(bot, callback_id, chat_id, message_id, user_id, data, message_text)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler."""

    def do_POST(self):
        """Handle POST requests from Telegram webhook."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            update_data = json.loads(body.decode('utf-8'))

            logger.info(f"Received update: {update_data.get('update_id')}")

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
