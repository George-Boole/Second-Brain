"""Vercel serverless function for external capture (Siri Shortcuts, etc.)."""

import json
import logging
import sys
import os

# Add bot directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bot'))

from http.server import BaseHTTPRequestHandler
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton

from config import TELEGRAM_BOT_TOKEN, validate_config
from classifier import classify_message, detect_completion_intent, detect_deletion_intent, detect_status_change_intent
from database import (
    log_to_inbox, route_to_category, update_inbox_log_processed,
    mark_task_done, find_task_by_title, find_item_for_deletion,
    delete_task, find_item_for_status_change, update_item_status,
    is_user_authorized,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CATEGORIES = ["people", "projects", "ideas", "admin"]
CATEGORY_EMOJI = {
    "people": "\U0001F464",
    "projects": "\U0001F4CB",
    "ideas": "\U0001F4A1",
    "admin": "\U00002705",
    "needs_review": "\U0001F914",
}


def build_fix_keyboard(inbox_log_id: str, current_category: str) -> list:
    """Build inline keyboard for category fix buttons."""
    buttons = []
    for cat in CATEGORIES:
        if cat != current_category:
            emoji = CATEGORY_EMOJI.get(cat, "")
            buttons.append(InlineKeyboardButton(
                text=f"{emoji} {cat}",
                callback_data=f"fix:{inbox_log_id}:{cat}"
            ))
    keyboard = [buttons[:2], buttons[2:]] if len(buttons) > 2 else [buttons]
    keyboard.append([InlineKeyboardButton(
        text="\u274C Cancel (delete)",
        callback_data=f"cancel:{inbox_log_id}"
    )])
    return keyboard


async def process_capture(user_id: int, text: str):
    """Process a captured message the same way as a normal Telegram message."""
    validate_config()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    chat_id = user_id  # Telegram chat_id == user_id for DMs

    # Check for natural language completion
    completion_check = detect_completion_intent(text)
    if completion_check.get("is_completion") and completion_check.get("task_hint"):
        task = find_task_by_title(completion_check["task_hint"], user_id)
        if task:
            result = mark_task_done(task["table"], task["id"], user_id)
            success = result.get("success", False) if isinstance(result, dict) else result
            next_occ = result.get("next_occurrence") if isinstance(result, dict) else None
            if success:
                msg = f"Marked done: *{task['title']}*\n\n_(Captured via Shortcut)_"
                if next_occ:
                    msg += f"\n\n\U0001F504 _Recurring: Next due {next_occ['date']}_"
                await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                return {"processed": "completion", "title": task["title"]}

    # Check for deletion intent
    deletion_check = detect_deletion_intent(text)
    if deletion_check.get("is_deletion") and deletion_check.get("task_hint"):
        item = find_item_for_deletion(deletion_check["task_hint"], user_id, deletion_check.get("table_hint"))
        if item:
            confirm_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(text="\u2705 Yes, delete", callback_data=f"confirm_del:{item['table']}:{item['id']}"),
                    InlineKeyboardButton(text="\u274C No, keep it", callback_data="cancel_del"),
                ]
            ])
            await bot.send_message(
                chat_id=chat_id,
                text=f"Found *{item['title']}* in {item['table']}.\n\nDelete it?",
                reply_markup=confirm_keyboard,
                parse_mode="Markdown"
            )
            return {"processed": "deletion_prompt", "title": item["title"]}

    # Check for status change intent
    status_check = detect_status_change_intent(text)
    if status_check.get("is_status_change") and status_check.get("task_hint") and status_check.get("new_status"):
        item = find_item_for_status_change(status_check["task_hint"], user_id, status_check.get("table_hint"))
        if item:
            updated = update_item_status(item["table"], item["id"], status_check["new_status"], user_id)
            if updated:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Updated *{item['title']}* to {status_check['new_status']}\n\n_(Captured via Shortcut)_",
                    parse_mode="Markdown"
                )
                return {"processed": "status_change", "title": item["title"]}

    # Check for "done:" prefix
    if text.lower().startswith("done:"):
        search_term = text[5:].strip()
        if search_term:
            task = find_task_by_title(search_term, user_id)
            if task:
                result = mark_task_done(task["table"], task["id"], user_id)
                success = result.get("success", False) if isinstance(result, dict) else result
                if success:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"Marked done: *{task['title']}*\n\n_(Captured via Shortcut)_",
                        parse_mode="Markdown"
                    )
                    return {"processed": "completion", "title": task["title"]}

    # Default: classify and route
    classification = classify_message(text, user_id)
    category = classification.get("category", "needs_review")
    confidence = classification.get("confidence", 0.0)
    title = classification.get("title", "Untitled")

    inbox_record = log_to_inbox(text, "shortcut", classification, user_id)
    inbox_log_id = inbox_record.get("id") if inbox_record else None

    if inbox_log_id:
        target_table, target_record = route_to_category(classification, inbox_log_id, user_id)
        if target_record:
            update_inbox_log_processed(inbox_log_id, target_table, target_record.get("id"))

    emoji = CATEGORY_EMOJI.get(category, "\U00002753")

    if category == "needs_review":
        reply = (
            f"{emoji} Captured for review\n\n"
            f"Title: {title}\n"
            f"Confidence: {confidence:.0%}\n\n"
            "I wasn't sure how to classify this. Tap a button to assign a category:"
        )
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

    return {"processed": "capture", "category": category, "title": title}


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for external capture."""

    def do_POST(self):
        """Handle POST requests from Siri Shortcuts, etc."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            user_id = data.get("user_id")
            text = data.get("text", "").strip()

            if not user_id or not text:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing user_id or text"}).encode())
                return

            user_id = int(user_id)

            # Verify authorization
            if not is_user_authorized(user_id):
                self.send_response(403)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
                return

            logger.info(f"Capture from user {user_id}: {text[:50]}...")

            import asyncio
            result = asyncio.run(process_capture(user_id, text))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, **result}).encode())

        except Exception as e:
            logger.error(f"Error handling capture: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self):
        """Health check."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "Capture endpoint active"}).encode())
