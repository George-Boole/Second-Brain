"""Telegram bot for Second Brain capture."""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config import TELEGRAM_BOT_TOKEN, validate_config
from classifier import classify_message
from database import log_to_inbox, route_to_category, update_inbox_log_processed

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
        "/help - This help text\n\n"
        "Category Prefixes:\n"
        "- person: Force people category\n"
        "- project: Force projects category\n"
        "- idea: Force ideas category\n"
        "- admin: Force admin category\n\n"
        "Just send any message to capture a thought!"
    )
    await update.message.reply_text(help_text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process incoming text messages."""
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

        # Step 5: Send confirmation
        emoji = CATEGORY_EMOJI.get(category, "\U00002753")

        if category == "needs_review":
            reply = (
                f"{emoji} Captured for review\n\n"
                f"Title: {title}\n"
                f"Confidence: {confidence:.0%}\n\n"
                "I wasn't sure how to classify this. It's saved in your inbox for manual review."
            )
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

        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(
            "Sorry, something went wrong processing your message. "
            "Please try again or check the logs."
        )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages - inform user about limitation."""
    await update.message.reply_text(
        "Voice messages received! However, I can't transcribe audio directly yet.\n\n"
        "For now, please send text messages. "
        "Voice transcription can be added with Whisper API integration."
    )


def main():
    """Start the bot."""
    # Validate configuration
    validate_config()

    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Start polling
    logger.info("Starting Second Brain Telegram Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
