"""Vercel cron function for recurring reminders."""

import json
import logging
import sys
import os
from datetime import datetime

# Add bot directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'bot'))

from http.server import BaseHTTPRequestHandler
from telegram import Bot

from config import TELEGRAM_BOT_TOKEN, ALLOWED_USER_IDS, validate_config
from database import get_due_reminders, update_reminder_sent, get_setting

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def should_send_now() -> bool:
    """Check if current local time is 2 PM (default reminder check time)."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz_name = get_setting("timezone") or "America/Denver"

    try:
        tz = ZoneInfo(tz_name)
        now_local = datetime.now(tz)
        # Reminders are checked at 2 PM local time
        return now_local.hour == 14
    except Exception as e:
        logger.error(f"Timezone error: {e}, falling back to UTC check")
        return datetime.utcnow().hour == 14


async def send_reminders_to_users():
    """Process due reminders and send to all authorized users."""
    validate_config()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    logger.info("Checking for due reminders...")

    try:
        reminders = get_due_reminders()

        if not reminders:
            logger.info("No due reminders found")
            return {"success": True, "reminders_sent": 0}

        sent_count = 0
        for reminder in reminders:
            reminder_id = reminder["id"]
            title = reminder["title"]
            recurrence = reminder["recurrence"]
            recurrence_day = reminder.get("recurrence_day")
            target_table = reminder.get("target_table")

            # Build reminder message
            emoji = "\U0001F514"  # bell emoji
            if target_table:
                emoji = {
                    "admin": "\u2705",
                    "projects": "\U0001F4CB",
                    "people": "\U0001F464"
                }.get(target_table, "\U0001F514")

            msg = f"{emoji} *Reminder*: {title}\n"
            msg += f"_({recurrence})_"

            # Send to all users
            for user_id in ALLOWED_USER_IDS:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=msg,
                        parse_mode="Markdown"
                    )
                    logger.info(f"Reminder '{title}' sent to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send reminder to {user_id}: {e}")

            # Update reminder with next occurrence
            update_reminder_sent(reminder_id, recurrence, recurrence_day)
            sent_count += 1

        return {"success": True, "reminders_sent": sent_count}

    except Exception as e:
        logger.error(f"Error processing reminders: {e}")
        return {"success": False, "error": str(e)}


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for cron."""

    def do_GET(self):
        """Handle GET requests from Vercel cron."""
        try:
            # Verify this is a Vercel cron request (optional security)
            auth_header = self.headers.get('Authorization')
            cron_secret = os.environ.get('CRON_SECRET')

            if cron_secret and auth_header != f'Bearer {cron_secret}':
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
                return

            logger.info("Cron triggered: processing reminders")

            # Process reminders
            import asyncio
            result = asyncio.run(send_reminders_to_users())

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            logger.error(f"Cron error: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
