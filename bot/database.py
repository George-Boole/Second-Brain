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
