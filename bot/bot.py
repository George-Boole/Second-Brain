"""Telegram bot for Second Brain capture."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from datetime import time, datetime
import pytz

from config import TELEGRAM_BOT_TOKEN, ALLOWED_USER_IDS, validate_config
from classifier import classify_message, detect_completion_intent
from database import (
    log_to_inbox, route_to_category, update_inbox_log_processed, reclassify_item,
    get_first_needs_review, get_all_pending_tasks, mark_task_done, find_task_by_title
)
from scheduler import generate_digest

# Timezone for scheduled digest
DIGEST_TIMEZONE = pytz.timezone("America/Denver")  # Mountain Time
DIGEST_HOUR = 7  # 7 AM
DIGEST_MINUTE = 0

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Category emoji mapping
CATEGORY_EMOJI = {
    "people": "\U0001F464",      # bust silhouette
    "projects": "\U0001F4CB",    # clipboard
    "ideas": "\U0001F4A1",       # light bulb
    "admin": "\U00002705",       # check mark
    "needs_review": "\U0001F914", # thinking face
}

# All routable categories (excluding needs_review)
CATEGORIES = ["people", "projects", "ideas", "admin"]


def build_fix_keyboard(inbox_log_id: str, current_category: str) -> InlineKeyboardMarkup:
    """Build inline keyboard with buttons to fix category."""
    buttons = []
    for cat in CATEGORIES:
        if cat != current_category:
            emoji = CATEGORY_EMOJI.get(cat, "")
            # callback_data format: fix:{inbox_log_id}:{new_category}
            buttons.append(InlineKeyboardButton(
                f"{emoji} {cat}",
                callback_data=f"fix:{inbox_log_id}:{cat}"
            ))
    # Arrange in 2x2 grid
    keyboard = [buttons[:2], buttons[2:]] if len(buttons) > 2 else [buttons]
    return InlineKeyboardMarkup(keyboard)


async def is_authorized(update: Update) -> bool:
    """Check if user is authorized to use the bot."""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        logger.warning(f"Unauthorized access attempt from user ID: {user_id}")
        await update.message.reply_text("Unauthorized. This bot is private.")
        return False
    return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome = (
        "Welcome to Second Brain!\n\n"
        "Send me any thought, idea, or note and I'll:\n"
        "1. Classify it (people/projects/ideas/admin)\n"
        "2. Store it in your database\n"
        "3. Confirm what was captured\n\n"
        "Tips:\n"
        "- Start with 'person:', 'project:', 'idea:', or 'admin:' to force a category\n"
        "- Just send text or voice messages anytime\n\n"
        "Try it now - send me a thought!"
    )
    await update.message.reply_text(welcome)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "*Second Brain Commands:*\n\n"
        "/start - Welcome message\n"
        "/help - This help text\n"
        "/digest - Get your daily digest\n"
        "/review - Classify items needing review\n"
        "/tasks - View pending tasks with done buttons\n\n"
        "*Category Prefixes:*\n"
        "`person:` Force people category\n"
        "`project:` Force projects category\n"
        "`idea:` Force ideas category\n"
        "`admin:` Force admin category\n\n"
        "*Mark Tasks Done:*\n"
        "`done: task name` - Mark a task complete\n\n"
        "Just send any message to capture a thought!\n"
        "Daily digest at 7 AM Mountain Time."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /digest command - generate and send daily digest."""
    if not await is_authorized(update):
        return

    logger.info(f"Digest requested by {update.effective_user.username}")

    # Send a "generating" message
    msg = await update.message.reply_text("🧠 Generating your digest...")

    try:
        digest = generate_digest()
        await msg.edit_text(digest, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error generating digest: {e}")
        await msg.edit_text(f"Error generating digest: {str(e)}")


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /review command - show items needing classification."""
    if not await is_authorized(update):
        return

    item = get_first_needs_review()

    if not item:
        await update.message.reply_text("✅ No items need review! All caught up.")
        return

    # Build message
    text = (
        f"🔍 *Needs Review*\n\n"
        f"*Title:* {item.get('ai_title', 'Unknown')}\n"
        f"*Message:* {item.get('raw_message', '')[:200]}\n"
        f"*Confidence:* {float(item.get('confidence', 0)):.0%}\n\n"
        f"Tap a category to classify:"
    )

    # Build keyboard with all categories
    keyboard = build_fix_keyboard(item["id"], "needs_review")

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /tasks command - show pending tasks with done buttons."""
    if not await is_authorized(update):
        return

    tasks = get_all_pending_tasks()

    if not tasks:
        await update.message.reply_text("✅ No pending tasks! You're all caught up.")
        return

    # Group by table
    admin_tasks = [t for t in tasks if t["table"] == "admin"]
    project_tasks = [t for t in tasks if t["table"] == "projects"]
    people_tasks = [t for t in tasks if t["table"] == "people"]

    # Build message with inline buttons
    text = "📋 *Pending Tasks*\n\n"

    buttons = []

    if admin_tasks:
        text += "⚡ *Admin:*\n"
        for t in admin_tasks[:5]:
            text += f"• {t['title']}"
            if t.get('due_date'):
                text += f" (due: {t['due_date']})"
            text += "\n"
            buttons.append([InlineKeyboardButton(
                f"✅ {t['title'][:25]}",
                callback_data=f"done:{t['table']}:{t['id']}"
            )])
        text += "\n"

    if project_tasks:
        text += "🚀 *Project Next Actions:*\n"
        for t in project_tasks[:5]:
            text += f"• {t['title']}: {t['detail'][:50]}\n"
            buttons.append([InlineKeyboardButton(
                f"✅ {t['title'][:25]}",
                callback_data=f"done:{t['table']}:{t['id']}"
            )])
        text += "\n"

    if people_tasks:
        text += "🤝 *Follow-ups:*\n"
        for t in people_tasks[:5]:
            text += f"• {t['title']}: {t['detail'][:50]}\n"
            buttons.append([InlineKeyboardButton(
                f"✅ {t['title'][:25]}",
                callback_data=f"done:{t['table']}:{t['id']}"
            )])

    text += "\n_Tap a button to mark done, or send:_\n`done: [task name]`"

    keyboard = InlineKeyboardMarkup(buttons) if buttons else None
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def send_scheduled_digest(context: ContextTypes.DEFAULT_TYPE):
    """Send the daily digest to all authorized users."""
    logger.info("Running scheduled daily digest...")

    try:
        digest = generate_digest()

        # Send to all authorized users
        for user_id in ALLOWED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=digest,
                    parse_mode="Markdown"
                )
                logger.info(f"Digest sent to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send digest to {user_id}: {e}")

    except Exception as e:
        logger.error(f"Error in scheduled digest: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process incoming text messages."""
    if not await is_authorized(update):
        return

    raw_message = update.message.text
    user = update.effective_user

    logger.info(f"Received message from {user.username}: {raw_message[:50]}...")

    # Check for "done:" prefix to mark tasks complete
    if raw_message.lower().startswith("done:"):
        search_term = raw_message[5:].strip()
        if search_term:
            task = find_task_by_title(search_term)
            if task:
                success = mark_task_done(task["table"], task["id"])
                if success:
                    await update.message.reply_text(
                        f"✅ Marked done: *{task['title']}*",
                        parse_mode="Markdown"
                    )
                else:
                    await update.message.reply_text("Failed to mark task done.")
            else:
                await update.message.reply_text(
                    f"Couldn't find a task matching \"{search_term}\".\n"
                    f"Try /tasks to see all pending tasks."
                )
        else:
            await update.message.reply_text("Usage: `done: task name`", parse_mode="Markdown")
        return

    # Check for natural language completion intent (AI-powered)
    completion_check = detect_completion_intent(raw_message)
    if completion_check.get("is_completion") and completion_check.get("task_hint"):
        search_term = completion_check["task_hint"]
        task = find_task_by_title(search_term)
        if task:
            success = mark_task_done(task["table"], task["id"])
            if success:
                await update.message.reply_text(
                    f"✅ Marked done: *{task['title']}*\n\n"
                    f"_(Detected from: \"{raw_message}\")_",
                    parse_mode="Markdown"
                )
                return
        # If no matching task found, fall through to capture as new thought
        logger.info(f"Completion detected but no task matched: {search_term}")

    try:
        # Step 1: Classify the message
        classification = classify_message(raw_message)
        category = classification.get("category", "needs_review")
        confidence = classification.get("confidence", 0.0)
        title = classification.get("title", "Untitled")

        logger.info(f"Classified as {category} ({confidence:.0%}): {title}")

        # Step 2: Log to inbox_log
        inbox_record = log_to_inbox(raw_message, "telegram", classification)
        inbox_log_id = inbox_record.get("id") if inbox_record else None

        # Step 3: Route to category table
        if inbox_log_id:
            target_table, target_record = route_to_category(classification, inbox_log_id)

            # Step 4: Update inbox_log with target info
            if target_record:
                update_inbox_log_processed(inbox_log_id, target_table, target_record.get("id"))

        # Step 5: Send confirmation with fix buttons
        emoji = CATEGORY_EMOJI.get(category, "\U00002753")

        if category == "needs_review":
            reply = (
                f"{emoji} Captured for review\n\n"
                f"Title: {title}\n"
                f"Confidence: {confidence:.0%}\n\n"
                "I wasn't sure how to classify this. Tap a button to assign a category:"
            )
            # Show all category buttons for needs_review
            keyboard = build_fix_keyboard(inbox_log_id, category) if inbox_log_id else None
        else:
            reply = (
                f"{emoji} Captured to {category}!\n\n"
                f"Title: {title}\n"
                f"Confidence: {confidence:.0%}"
            )

            # Add extra details based on category
            if category == "projects" and classification.get("next_action"):
                reply += f"\nNext: {classification.get('next_action')}"
            if classification.get("due_date"):
                reply += f"\nDue: {classification.get('due_date')}"

            reply += "\n\nWrong category? Tap to fix:"
            keyboard = build_fix_keyboard(inbox_log_id, category) if inbox_log_id else None

        await update.message.reply_text(reply, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong processing your message. "
            "Please try again or check the logs."
        )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages - inform user about limitation."""
    if not await is_authorized(update):
        return

    await update.message.reply_text(
        "Voice messages received! However, I can't transcribe audio directly yet.\n\n"
        "For now, please send text messages. "
        "Voice transcription can be added with Whisper API integration."
    )


async def handle_fix_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category fix button presses."""
    query = update.callback_query
    await query.answer()

    # Check authorization
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        logger.warning(f"Unauthorized callback from user ID: {user_id}")
        return

    # Parse callback data: fix:{inbox_log_id}:{new_category}
    data = query.data
    if not data.startswith("fix:"):
        return

    parts = data.split(":")
    if len(parts) != 3:
        return

    _, inbox_log_id, new_category = parts

    try:
        # Reclassify the item
        result = reclassify_item(inbox_log_id, new_category)

        if result:
            emoji = CATEGORY_EMOJI.get(new_category, "")
            new_text = (
                f"{emoji} Moved to {new_category}!\n\n"
                f"Title: {result.get('ai_title', 'Unknown')}\n"
                f"(Manually reclassified)"
            )
            await query.edit_message_text(new_text)

            # If this was from /review, show the next item
            next_item = get_first_needs_review()
            if next_item:
                text = (
                    f"🔍 *Next item to review:*\n\n"
                    f"*Title:* {next_item.get('ai_title', 'Unknown')}\n"
                    f"*Message:* {next_item.get('raw_message', '')[:200]}\n\n"
                    f"Tap a category:"
                )
                keyboard = build_fix_keyboard(next_item["id"], "needs_review")
                await query.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await query.edit_message_text("Failed to reclassify. Please try again.")

    except Exception as e:
        logger.error(f"Error reclassifying item: {e}")
        await query.edit_message_text(f"Error: {str(e)}")


async def handle_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle done button presses for tasks."""
    query = update.callback_query
    await query.answer()

    # Check authorization
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        return

    # Parse callback data: done:{table}:{id}
    data = query.data
    if not data.startswith("done:"):
        return

    parts = data.split(":")
    if len(parts) != 3:
        return

    _, table, task_id = parts

    try:
        success = mark_task_done(table, task_id)

        if success:
            # Update the button to show it's done
            await query.edit_message_text(
                query.message.text + f"\n\n✅ _Marked complete!_",
                parse_mode="Markdown"
            )
        else:
            await query.answer("Failed to mark done", show_alert=True)

    except Exception as e:
        logger.error(f"Error marking task done: {e}")
        await query.answer(f"Error: {str(e)}", show_alert=True)


def main():
    """Start the bot."""
    # Validate configuration
    validate_config()

    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("digest", digest_command))
    app.add_handler(CommandHandler("review", review_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(CallbackQueryHandler(handle_fix_callback, pattern="^fix:"))
    app.add_handler(CallbackQueryHandler(handle_done_callback, pattern="^done:"))

    # Schedule daily digest at 7 AM Mountain Time
    job_queue = app.job_queue
    digest_time = time(hour=DIGEST_HOUR, minute=DIGEST_MINUTE, tzinfo=DIGEST_TIMEZONE)
    job_queue.run_daily(send_scheduled_digest, time=digest_time, name="daily_digest")
    logger.info(f"Daily digest scheduled for {DIGEST_HOUR}:{DIGEST_MINUTE:02d} AM Mountain Time")

    # Start polling
    logger.info("Starting Second Brain Telegram Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
