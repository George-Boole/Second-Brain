"""Daily digest scheduler for Second Brain."""

import json
from datetime import datetime
from openai import OpenAI
from config import OPENAI_API_KEY
from database import (
    get_active_projects,
    get_follow_ups,
    get_pending_admin,
    get_random_idea,
    get_needs_review,
    get_completed_today,
    get_tomorrow_priorities,
    get_overdue_items,
    get_completed_this_week,
    get_high_priority_items,
    get_random_someday_item,
)

client = OpenAI(api_key=OPENAI_API_KEY)

DIGEST_PROMPT = """You are the "Second Brain" Morning Digest Assistant. Your goal is to provide a concise, motivating, and actionable summary of the user's brain state.

INPUT DATA STRUCTURE:
You will receive JSON data containing results from database queries:
1. Active Projects (from projects table)
2. Follow-ups (from people table)
3. Pending Tasks (from admin table)
4. Random Idea (the "spark")
5. Items Needing Review

YOUR OUTPUT FORMAT:
- Use a friendly but professional tone.
- Use Telegram-friendly markdown (bold with *, bullet points with •).
- Keep it concise and scannable.

SECTIONS:
1. 🌅 *Good Morning* - A 1-sentence vibe check based on what's on the plate.
2. 🚀 *Active Projects* - Top items with their "Next Action".
3. 🤝 *People to Contact* - All active people. Highlight overdue/due follow-ups first, then list others.
4. ⚡ *Quick Admin* - Pending tasks with upcoming due dates.
5. 💡 *Random Spark* - One random idea from the vault (if provided).
6. 🔍 *Needs Review* - Items awaiting classification (if any).

CONSTRAINTS:
- Do not make up information. Only use what's provided.
- If a section has no items, say "All clear!" or skip it.
- Focus on ACTION - what should the user do today?
- Keep the entire digest under 200 words.
- Today's date is {today}.

INPUT JSON:
{data}"""


def gather_digest_data(user_id: int) -> dict:
    """Gather all data needed for the daily digest for a specific user."""
    return {
        "projects": get_active_projects(user_id),
        "follow_ups": get_follow_ups(user_id),
        "admin_tasks": get_pending_admin(user_id),
        "random_idea": get_random_idea(user_id),
        "needs_review": get_needs_review(user_id),
    }


def format_digest(data: dict) -> str:
    """Use OpenAI to format the digest data into a readable message."""
    today = datetime.now().strftime("%A, %B %d, %Y")

    prompt = DIGEST_PROMPT.format(
        today=today,
        data=json.dumps(data, indent=2, default=str)
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate the morning digest."}
            ],
            temperature=0.7,
            max_tokens=800,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating digest: {str(e)}"


def generate_digest(user_id: int) -> str:
    """Main function to generate the complete daily digest for a specific user."""
    data = gather_digest_data(user_id)
    return format_digest(data)


# ============================================
# Evening Recap
# ============================================

EVENING_RECAP_PROMPT = """You are the "Second Brain" Evening Recap Assistant. Your goal is to provide a calming, reflective summary of the day and set up tomorrow.

INPUT DATA STRUCTURE:
You will receive JSON data containing:
1. Items completed today (admin, projects, people, ideas)
2. Tomorrow's priorities (high priority or due tomorrow)
3. Overdue items needing attention

YOUR OUTPUT FORMAT:
- Use a warm, encouraging but concise tone.
- Use Telegram-friendly markdown (bold with *, bullet points with •).
- Keep it scannable and brief.

SECTIONS:
1. 🌙 *Evening Check-in* - 1-sentence acknowledgment of the day
2. ✅ *Today's Wins* - What got completed today (if any)
3. 📋 *Tomorrow's Focus* - Top 3 priorities for tomorrow
4. ⚠️ *Needs Attention* - Overdue items (brief, max 3)
5. 💤 *Wind Down* - Brief encouraging sign-off (1 sentence)

CONSTRAINTS:
- Do not make up information. Only use what's provided.
- If a section has no items, skip it entirely or say "Nothing to report!"
- Focus on being encouraging, not overwhelming
- Keep the entire recap under 150 words.
- Today's date is {today}.

INPUT JSON:
{data}"""


def gather_evening_data(user_id: int) -> dict:
    """Gather all data needed for the evening recap for a specific user."""
    return {
        "completed_today": get_completed_today(user_id),
        "tomorrow_priorities": get_tomorrow_priorities(user_id),
        "overdue_items": get_overdue_items(user_id),
    }


def format_evening_recap(data: dict) -> str:
    """Use OpenAI to format the evening recap data into a readable message."""
    today = datetime.now().strftime("%A, %B %d, %Y")

    prompt = EVENING_RECAP_PROMPT.format(
        today=today,
        data=json.dumps(data, indent=2, default=str)
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate the evening recap."}
            ],
            temperature=0.7,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating evening recap: {str(e)}"


def generate_evening_recap(user_id: int) -> str:
    """Main function to generate the complete evening recap for a specific user."""
    data = gather_evening_data(user_id)
    return format_evening_recap(data)


# ============================================
# Weekly Review
# ============================================

WEEKLY_REVIEW_PROMPT = """You are the "Second Brain" Weekly Review Assistant. Your goal is to provide a reflective summary of the week and set priorities for the next week.

INPUT DATA STRUCTURE:
You will receive JSON data containing:
1. Items completed this week (admin, projects, people, ideas)
2. High priority items for next week
3. A random "someday" item to consider

YOUR OUTPUT FORMAT:
- Use a warm, reflective but forward-looking tone.
- Use Telegram-friendly markdown (bold with *, bullet points with •).
- Keep it scannable and motivating.

SECTIONS:
1. 📅 *Weekly Review* - Date range and 1-sentence summary
2. 🏆 *This Week's Wins* - What got completed (celebrate accomplishments!)
3. ⚡ *High Priority Next Week* - Items flagged as high priority
4. 💭 *From the Someday List* - Surface one someday item to reconsider
5. 🎯 *Focus for the Week* - Brief encouraging sign-off (1 sentence)

CONSTRAINTS:
- Do not make up information. Only use what's provided.
- If a section has no items, skip it or say "Nothing to report!"
- Be encouraging about accomplishments
- Keep the entire review under 200 words.
- Today's date is {today}.

INPUT JSON:
{data}"""


def gather_weekly_data(user_id: int) -> dict:
    """Gather all data needed for the weekly review for a specific user."""
    return {
        "completed_this_week": get_completed_this_week(user_id),
        "high_priority": get_high_priority_items(user_id),
        "someday_item": get_random_someday_item(user_id),
    }


def format_weekly_review(data: dict) -> str:
    """Use OpenAI to format the weekly review data into a readable message."""
    today = datetime.now().strftime("%A, %B %d, %Y")

    prompt = WEEKLY_REVIEW_PROMPT.format(
        today=today,
        data=json.dumps(data, indent=2, default=str)
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate the weekly review."}
            ],
            temperature=0.7,
            max_tokens=800,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating weekly review: {str(e)}"


def generate_weekly_review(user_id: int) -> str:
    """Main function to generate the complete weekly review for a specific user."""
    data = gather_weekly_data(user_id)
    return format_weekly_review(data)
