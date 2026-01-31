"""Telegram bot for Second Brain capture."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from datetime import time, datetime
import pytz

from config import TELEGRAM_BOT_TOKEN, ALLOWED_USER_IDS, validate_config
from classifier import classify_message
from database import log_to_inbox, route_to_category, update_inbox_log_processed, reclassify_item
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
        "Second Brain Commands:\n\n"
        "/start - Welcome message\n"
        "/help - This help text\n"
        "/digest - Get your daily digest now\n\n"
        "Category Prefixes:\n"
        "- person: Force people category\n"
        "- project: Force projects category\n"
        "- idea: Force ideas category\n"
        "- admin: Force admin category\n\n"
        "Just send any message to capture a thought!\n\n"
        "Daily digest is sent automatically at 7 AM Mountain Time."
    )
    await update.message.reply_text(help_text)


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
        else:
            await query.edit_message_text("Failed to reclassify. Please try again.")

    except Exception as e:
        logger.error(f"Error reclassifying item: {e}")
        await query.edit_message_text(f"Error: {str(e)}")


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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(CallbackQueryHandler(handle_fix_callback, pattern="^fix:"))

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
