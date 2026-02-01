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
3. 🤝 *People to Contact* - Anyone needing follow-up today or overdue.
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


def gather_digest_data() -> dict:
    """Gather all data needed for the daily digest."""
    return {
        "projects": get_active_projects(),
        "follow_ups": get_follow_ups(),
        "admin_tasks": get_pending_admin(),
        "random_idea": get_random_idea(),
        "needs_review": get_needs_review(),
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


def generate_digest() -> str:
    """Main function to generate the complete daily digest."""
    data = gather_digest_data()
    return format_digest(data)
