"""Vercel cron function for evening recap."""

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
from scheduler import generate_evening_recap
from database import get_setting

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def should_send_now(hour_setting_key: str, user_id: int = None) -> bool:
    """Check if current local time matches the configured hour for a specific user."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz_name = get_setting("timezone", user_id) or "America/Denver"
    target_hour = int(get_setting(hour_setting_key, user_id) or "21")

    try:
        tz = ZoneInfo(tz_name)
        now_local = datetime.now(tz)
        return now_local.hour == target_hour
    except Exception as e:
        logger.error(f"Timezone error: {e}, falling back to UTC check")
        return datetime.utcnow().hour == target_hour


async def send_evening_recap_to_users():
    """Generate and send personalized evening recap to all authorized users."""
    validate_config()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    logger.info("Generating personalized evening recaps for each user...")
    sent_count = 0

    try:
        for user_id in ALLOWED_USER_IDS:
            try:
                # Generate personalized recap for this user
                recap = generate_evening_recap(user_id)
                await bot.send_message(
                    chat_id=user_id,
                    text=recap,
                    parse_mode="Markdown"
                )
                logger.info(f"Evening recap sent to user {user_id}")
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send recap to {user_id}: {e}")

        return {"success": True, "recipients": sent_count}

    except Exception as e:
        logger.error(f"Error generating evening recap: {e}")
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

            logger.info("Cron triggered: sending evening recap")

            # Send the recap
            import asyncio
            result = asyncio.run(send_evening_recap_to_users())

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
