"""OpenAI-powered message classifier for Second Brain."""

import json
from openai import OpenAI
from config import OPENAI_API_KEY

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Classification prompt template - {today} will be replaced with current date
SYSTEM_PROMPT = """You are a classification assistant for a "Second Brain" system. Your job is to categorize messages into one of the following tables.

TODAY'S DATE: {today}

CATEGORIES:
- people: Tasks about CONTACTING or FOLLOWING UP with a specific person (call someone, meet someone, check in with someone). Also use for relationship notes and info about people.
- projects: Multi-step work, ongoing initiatives, goals with multiple tasks
- ideas: Thoughts, insights, concepts to explore later, creative inspiration
- admin: Simple one-off tasks NOT about contacting people (pay bills, buy groceries, schedule appointments, errands)

PEOPLE vs ADMIN DECISION:
- "Call Rachel today" → PEOPLE (it's about contacting a person)
- "Meet John for coffee" → PEOPLE (it's about a person)
- "Follow up with Sarah" → PEOPLE (it's about contacting a person)
- "Buy groceries for mom" → ADMIN (task is about groceries, not about mom)
- "Pay the electric bill" → ADMIN (impersonal task)
- "Schedule dentist appointment" → ADMIN (impersonal task)

DATE EXTRACTION - CRITICAL:
Convert relative dates to YYYY-MM-DD format using today's date ({today}):
- "today" → {today}
- "tomorrow" → calculate from {today}
- "next week" → calculate from {today}
- "Monday" → next occurrence from {today}
ALWAYS extract and include dates when mentioned!

CONFIDENCE SCORING:
- 0.9-1.0: Very clear category
- 0.7-0.89: Fairly confident
- 0.5-0.69: Uncertain
- Below 0.6: Set category to "needs_review"

RULES:
1. Generate a concise title (just the task/topic, not "Reminder to...")
2. Extract dates and convert to YYYY-MM-DD
3. Output ONLY valid JSON - no markdown
4. PREFIX OVERRIDE: "person:", "project:", "idea:", "admin:" forces that category

JSON FORMAT (return ONLY this):

For PEOPLE:
{{"category": "people", "confidence": 0.85, "title": "Person's Name or Call [Name]", "summary": "Context", "follow_up": "What to follow up on", "follow_up_date": "YYYY-MM-DD or null"}}

For PROJECTS:
{{"category": "projects", "confidence": 0.85, "title": "Project Name", "summary": "Description", "next_action": "Next step", "due_date": "YYYY-MM-DD or null"}}

For IDEAS:
{{"category": "ideas", "confidence": 0.85, "title": "Idea Title", "summary": "Core insight"}}

For ADMIN:
{{"category": "admin", "confidence": 0.85, "title": "Task Name", "summary": "Context", "due_date": "YYYY-MM-DD or null"}}

For NEEDS_REVIEW:
{{"category": "needs_review", "confidence": 0.45, "title": "Description", "summary": "Original message", "possible_categories": ["cat1", "cat2"], "reason": "Why uncertain"}}"""


def detect_completion_intent(raw_message: str) -> dict:
    """
    Check if a message is about completing/finishing a task.
    Returns {"is_completion": bool, "task_hint": str or None}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """Analyze if this message describes something the user HAS DONE (past tense).

IMPORTANT: Any past-tense statement about an action the user took should be treated as a potential task completion. We will check if it matches an existing task - if not, it will be captured as a new item. So be AGGRESSIVE about marking things as completions.

COMPLETION - any past-tense "I did X" statement:
- "I called Rachel" → completion, task: "Rachel" or "call Rachel"
- "I sneezed" → completion, task: "sneeze"
- "I bought milk" → completion, task: "milk" or "buy milk"
- "Finished the patio estimate" → completion, task: "patio estimate"
- "Take Call Rachel off my list" → completion, task: "Call Rachel"
- "Done with the budget review" → completion, task: "budget review"
- "I did the grocery shopping" → completion, task: "grocery shopping"
- "I switched it" → completion, task: "switch"
- "Paid the bill" → completion, task: "bill" or "pay bill"

NOT completion (future tense, reminders, ideas):
- "I need to call Rachel tomorrow" → NOT completion (future intent)
- "Remind me about the patio" → NOT completion (request)
- "I have an idea for a new app" → NOT completion (idea)
- "Call Rachel" → NOT completion (command/request)

Extract the KEY NOUN or ACTION as the task_hint. Keep it short (1-3 words).

Return ONLY valid JSON:
{"is_completion": true/false, "task_hint": "extracted task name or null"}"""},
                {"role": "user", "content": raw_message}
            ],
            temperature=0.1,
            max_tokens=100,
        )

        content = response.choices[0].message.content.strip()
        import json
        return json.loads(content)

    except Exception:
        return {"is_completion": False, "task_hint": None}


def classify_message(raw_message: str) -> dict:
    """
    Classify a message using OpenAI GPT-4.
    Returns parsed JSON classification.
    """
    from datetime import date
    today = date.today().isoformat()

    try:
        # Insert today's date into the prompt
        prompt_with_date = SYSTEM_PROMPT.format(today=today)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_with_date},
                {"role": "user", "content": raw_message}
            ],
            temperature=0.3,
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON response
        classification = json.loads(content)
        return classification

    except json.JSONDecodeError as e:
        # If JSON parsing fails, return needs_review
        return {
            "category": "needs_review",
            "confidence": 0.0,
            "title": "Parse Error",
            "summary": raw_message,
            "reason": f"Failed to parse AI response: {str(e)}"
        }

    except Exception as e:
        # For any other error, return needs_review
        return {
            "category": "needs_review",
            "confidence": 0.0,
            "title": "Classification Error",
            "summary": raw_message,
            "reason": f"Classification failed: {str(e)}"
        }
