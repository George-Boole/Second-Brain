"""OpenAI-powered message classifier for Second Brain."""

import json
from openai import OpenAI
from config import OPENAI_API_KEY

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Classification prompt template
SYSTEM_PROMPT = """You are a classification assistant for a "Second Brain" system. Your job is to take a raw transcription of a voice message and categorize it into one of the following tables.

CATEGORIES:
- people: Information about a person, relationship update, something someone said, follow-up reminders
- projects: A project, task with multiple steps, ongoing work, goals with deadlines
- ideas: A thought, insight, concept, something to explore later, creative inspiration
- admin: Simple errand, one-off task, bills, appointments, life admin

CONFIDENCE SCORING:
- 0.9-1.0: Very clear category, obvious classification
- 0.7-0.89: Fairly confident, good match
- 0.5-0.69: Uncertain, could be multiple categories
- Below 0.5: Very unclear, needs human review

CRITICAL RULE: If confidence is below 0.6, set category to "needs_review"

RULES:
1. Analyze the message carefully
2. Generate a concise, descriptive title for the entry
3. Determine the best category based on content
4. Estimate confidence (0.0 to 1.0)
5. If a person's name is mentioned, consider if this is really about that PERSON or about a project/task involving them
6. "next_action" for projects must be specific and executable
7. Extract dates when mentioned and format as YYYY-MM-DD
8. Output ONLY valid JSON - no markdown, no explanation
9. PREFIX OVERRIDE: If the message starts with "person:", "project:", "idea:", or "admin:", use that category with confidence 1.0 and strip the prefix from the title/summary.

JSON FORMAT (return ONLY this, nothing else):

For PEOPLE:
{"category": "people", "confidence": 0.85, "title": "Person's Name", "summary": "Context about who they are", "follow_up": "What to follow up on or null"}

For PROJECTS:
{"category": "projects", "confidence": 0.85, "title": "Project Name", "summary": "Project description", "next_action": "Specific next action", "due_date": "YYYY-MM-DD or null"}

For IDEAS:
{"category": "ideas", "confidence": 0.85, "title": "Idea Title", "summary": "Core insight or elaboration"}

For ADMIN:
{"category": "admin", "confidence": 0.85, "title": "Task Name", "summary": "Additional context", "due_date": "YYYY-MM-DD or null"}

For NEEDS_REVIEW:
{"category": "needs_review", "confidence": 0.45, "title": "Brief description", "summary": "The original message", "possible_categories": ["category1", "category2"], "reason": "Why classification is uncertain"}"""


def detect_completion_intent(raw_message: str) -> dict:
    """
    Check if a message is about completing/finishing a task.
    Returns {"is_completion": bool, "task_hint": str or None}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """Analyze if this message indicates the user has COMPLETED or FINISHED a task, or wants to mark something as DONE.

Examples of completion messages:
- "I called Rachel" → completion, task: "Rachel" or "Call Rachel"
- "Finished the patio estimate" → completion, task: "patio estimate"
- "Take Call Rachel off my list" → completion, task: "Call Rachel"
- "Done with the budget review" → completion, task: "budget review"
- "I did the grocery shopping" → completion, task: "grocery shopping"

Examples of NON-completion messages (new tasks/thoughts):
- "I need to call Rachel tomorrow" → NOT completion
- "Remind me about the patio" → NOT completion
- "I have an idea for a new app" → NOT completion

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
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
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
