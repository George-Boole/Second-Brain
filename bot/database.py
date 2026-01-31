"""Supabase database operations for Second Brain."""

from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def log_to_inbox(raw_message: str, source: str, classification: dict) -> dict:
    """
    Log every incoming message to inbox_log (audit trail).
    Returns the created record.
    """
    data = {
        "raw_message": raw_message,
        "source": source,
        "category": classification.get("category"),
        "confidence": classification.get("confidence"),
        "ai_title": classification.get("title"),
        "ai_response": classification,
        "processed": False,
    }

    result = supabase.table("inbox_log").insert(data).execute()
    return result.data[0] if result.data else None


def insert_person(classification: dict, inbox_log_id: str) -> dict:
    """Insert a record into the people table."""
    data = {
        "name": classification.get("title"),
        "notes": classification.get("summary"),
        "follow_up_reason": classification.get("follow_up"),
        "inbox_log_id": inbox_log_id,
    }

    result = supabase.table("people").insert(data).execute()
    return result.data[0] if result.data else None


def insert_project(classification: dict, inbox_log_id: str) -> dict:
    """Insert a record into the projects table."""
    data = {
        "title": classification.get("title"),
        "description": classification.get("summary"),
        "next_action": classification.get("next_action"),
        "due_date": classification.get("due_date"),
        "status": "active",
        "priority": "medium",
        "inbox_log_id": inbox_log_id,
    }

    result = supabase.table("projects").insert(data).execute()
    return result.data[0] if result.data else None


def insert_idea(classification: dict, inbox_log_id: str) -> dict:
    """Insert a record into the ideas table."""
    data = {
        "title": classification.get("title"),
        "content": classification.get("summary"),
        "status": "captured",
        "inbox_log_id": inbox_log_id,
    }

    result = supabase.table("ideas").insert(data).execute()
    return result.data[0] if result.data else None


def insert_admin(classification: dict, inbox_log_id: str) -> dict:
    """Insert a record into the admin table."""
    data = {
        "title": classification.get("title"),
        "description": classification.get("summary"),
        "due_date": classification.get("due_date"),
        "status": "pending",
        "priority": "medium",
        "inbox_log_id": inbox_log_id,
    }

    result = supabase.table("admin").insert(data).execute()
    return result.data[0] if result.data else None


def update_inbox_log_processed(inbox_log_id: str, target_table: str, target_id: str):
    """Mark inbox_log entry as processed with target info."""
    supabase.table("inbox_log").update({
        "processed": True,
        "target_table": target_table,
        "target_id": target_id,
    }).eq("id", inbox_log_id).execute()


def route_to_category(classification: dict, inbox_log_id: str) -> tuple:
    """
    Route classification to appropriate table.
    Returns (target_table, target_record).
    """
    category = classification.get("category")

    if category == "people":
        record = insert_person(classification, inbox_log_id)
        return ("people", record)

    elif category == "projects":
        record = insert_project(classification, inbox_log_id)
        return ("projects", record)

    elif category == "ideas":
        record = insert_idea(classification, inbox_log_id)
        return ("ideas", record)

    elif category == "admin":
        record = insert_admin(classification, inbox_log_id)
        return ("admin", record)

    else:  # needs_review or unknown
        return ("inbox_log", None)


def get_active_projects(limit: int = 5) -> list:
    """Get active projects with their next actions."""
    result = supabase.table("projects").select(
        "title, next_action, due_date"
    ).eq("status", "active").order(
        "due_date", desc=False
    ).limit(limit).execute()
    return result.data if result.data else []


def get_follow_ups() -> list:
    """Get people needing follow-up (today or overdue)."""
    from datetime import date
    today = date.today().isoformat()
    result = supabase.table("people").select(
        "name, follow_up_reason, follow_up_date"
    ).lte("follow_up_date", today).order(
        "follow_up_date", desc=False
    ).execute()
    return result.data if result.data else []


def get_pending_admin(limit: int = 5) -> list:
    """Get pending admin tasks."""
    result = supabase.table("admin").select(
        "title, description, due_date"
    ).eq("status", "pending").order(
        "due_date", desc=False
    ).limit(limit).execute()
    return result.data if result.data else []


def get_random_idea() -> dict:
    """Get a random idea for the 'spark' section."""
    # Supabase doesn't have RANDOM() in the client, so we fetch a few and pick one
    result = supabase.table("ideas").select("title, content").limit(10).execute()
    if result.data:
        import random
        return random.choice(result.data)
    return None


def get_needs_review(limit: int = 5) -> list:
    """Get items needing manual review."""
    result = supabase.table("inbox_log").select(
        "id, ai_title, raw_message, confidence, created_at"
    ).eq("category", "needs_review").eq(
        "processed", False
    ).order("created_at", desc=True).limit(limit).execute()
    return result.data if result.data else []


def reclassify_item(inbox_log_id: str, new_category: str) -> dict:
    """
    Move an item from its current category to a new one.
    Returns the updated inbox_log record.
    """
    # Get the current inbox_log record
    result = supabase.table("inbox_log").select("*").eq("id", inbox_log_id).execute()
    if not result.data:
        return None

    inbox_record = result.data[0]
    old_table = inbox_record.get("target_table")
    old_id = inbox_record.get("target_id")

    # Delete from old category table if it was routed
    if old_table and old_id and old_table != "inbox_log":
        supabase.table(old_table).delete().eq("id", old_id).execute()

    # Build classification dict from inbox_log data
    ai_response = inbox_record.get("ai_response", {})
    if isinstance(ai_response, str):
        import json
        try:
            ai_response = json.loads(ai_response)
        except:
            ai_response = {}

    classification = {
        "category": new_category,
        "title": inbox_record.get("ai_title") or ai_response.get("title", "Untitled"),
        "summary": ai_response.get("summary", inbox_record.get("raw_message", "")),
        "confidence": 1.0,  # Manual classification is 100% confident
        "next_action": ai_response.get("next_action"),
        "due_date": ai_response.get("due_date"),
        "follow_up": ai_response.get("follow_up"),
    }

    # Route to new category
    new_table, new_record = route_to_category(classification, inbox_log_id)

    # Update inbox_log with new category and target
    supabase.table("inbox_log").update({
        "category": new_category,
        "confidence": 1.0,
        "processed": True,
        "target_table": new_table,
        "target_id": new_record.get("id") if new_record else None,
    }).eq("id", inbox_log_id).execute()

    # Return updated inbox record
    inbox_record["category"] = new_category
    inbox_record["target_table"] = new_table
    return inbox_record
