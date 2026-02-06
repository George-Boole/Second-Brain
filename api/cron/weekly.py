"""Vercel cron function for weekly review (Sunday afternoon)."""

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
from scheduler import generate_weekly_review

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def send_weekly_review_to_users():
    """Generate and send personalized weekly review to all authorized users."""
    validate_config()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    logger.info("Generating personalized weekly reviews for each user...")
    sent_count = 0

    try:
        for user_id in ALLOWED_USER_IDS:
            try:
                # Generate personalized weekly review for this user
                weekly = generate_weekly_review(user_id)
                await bot.send_message(
                    chat_id=user_id,
                    text=weekly,
                    parse_mode="Markdown"
                )
                logger.info(f"Weekly review sent to user {user_id}")
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send weekly review to {user_id}: {e}")

        return {"success": True, "recipients": sent_count}

    except Exception as e:
        logger.error(f"Error generating weekly review: {e}")
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

            logger.info("Cron triggered: sending weekly review")

            # Send the weekly review
            import asyncio
            result = asyncio.run(send_weekly_review_to_users())

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
