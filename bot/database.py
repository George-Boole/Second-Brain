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
        "follow_up_date": classification.get("follow_up_date"),
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


def get_first_needs_review() -> dict:
    """Get the first item needing review."""
    result = supabase.table("inbox_log").select(
        "id, ai_title, raw_message, confidence, created_at"
    ).eq("category", "needs_review").eq(
        "processed", False
    ).order("created_at", desc=False).limit(1).execute()
    return result.data[0] if result.data else None


def get_all_pending_tasks() -> list:
    """Get all pending tasks across tables for the /tasks command."""
    tasks = []

    # Admin tasks
    admin_result = supabase.table("admin").select(
        "id, title, description, due_date"
    ).eq("status", "pending").order("due_date", desc=False).limit(10).execute()
    for item in (admin_result.data or []):
        tasks.append({
            "id": item["id"],
            "table": "admin",
            "title": item["title"],
            "detail": item.get("description") or "",
            "due_date": item.get("due_date"),
        })

    # Active projects (with next_action as the "task")
    projects_result = supabase.table("projects").select(
        "id, title, next_action, due_date"
    ).eq("status", "active").order("due_date", desc=False).limit(10).execute()
    for item in (projects_result.data or []):
        if item.get("next_action"):
            tasks.append({
                "id": item["id"],
                "table": "projects",
                "title": item["title"],
                "detail": item.get("next_action") or "",
                "due_date": item.get("due_date"),
            })

    # People follow-ups
    from datetime import date
    today = date.today().isoformat()
    people_result = supabase.table("people").select(
        "id, name, follow_up_reason, follow_up_date"
    ).lte("follow_up_date", today).order("follow_up_date", desc=False).limit(10).execute()
    for item in (people_result.data or []):
        tasks.append({
            "id": item["id"],
            "table": "people",
            "title": f"Follow up: {item['name']}",
            "detail": item.get("follow_up_reason") or "",
            "due_date": item.get("follow_up_date"),
        })

    return tasks


def mark_task_done(table: str, task_id: str) -> bool:
    """Mark a task as done in the appropriate table."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Marking task done: table={table}, id={task_id}")

        if table == "admin":
            result = supabase.table("admin").update({"status": "completed"}).eq("id", task_id).execute()
        elif table == "projects":
            # For projects, clear the next_action (project itself stays active)
            result = supabase.table("projects").update({"next_action": None}).eq("id", task_id).execute()
        elif table == "people":
            # Clear the follow-up date
            result = supabase.table("people").update({"follow_up_date": None, "follow_up_reason": None}).eq("id", task_id).execute()
        else:
            logger.error(f"Unknown table: {table}")
            return False

        # Check if any rows were actually updated
        if result.data:
            logger.info(f"Successfully marked done: {result.data}")
            return True
        else:
            logger.warning(f"No rows updated for table={table}, id={task_id}")
            return False

    except Exception as e:
        logger.error(f"Error marking task done: {e}")
        return False


def find_item_for_deletion(search_term: str, table_hint: str = None) -> dict:
    """
    Search for an item to delete across tables.
    If table_hint is provided, only search that table.
    Returns {"id": ..., "table": ..., "title": ...} or None.
    """
    search_lower = search_term.lower()
    tables_to_search = [table_hint] if table_hint else ["admin", "projects", "people", "ideas"]

    for table in tables_to_search:
        if table == "admin":
            result = supabase.table("admin").select("id, title").execute()
            for item in (result.data or []):
                if search_lower in item["title"].lower():
                    return {"id": item["id"], "table": "admin", "title": item["title"]}

        elif table == "projects":
            result = supabase.table("projects").select("id, title").execute()
            for item in (result.data or []):
                if search_lower in item["title"].lower():
                    return {"id": item["id"], "table": "projects", "title": item["title"]}

        elif table == "people":
            result = supabase.table("people").select("id, name").execute()
            for item in (result.data or []):
                if search_lower in item["name"].lower():
                    return {"id": item["id"], "table": "people", "title": item["name"]}

        elif table == "ideas":
            result = supabase.table("ideas").select("id, title").execute()
            for item in (result.data or []):
                if search_lower in item["title"].lower():
                    return {"id": item["id"], "table": "ideas", "title": item["title"]}

    return None


def find_task_by_title(search_term: str) -> dict:
    """Fuzzy search for a task by title across all tables."""
    search_lower = search_term.lower()

    # Search admin tasks
    admin_result = supabase.table("admin").select("id, title").eq("status", "pending").execute()
    for item in (admin_result.data or []):
        if search_lower in item["title"].lower():
            return {"id": item["id"], "table": "admin", "title": item["title"]}

    # Search projects
    projects_result = supabase.table("projects").select("id, title").eq("status", "active").execute()
    for item in (projects_result.data or []):
        if search_lower in item["title"].lower():
            return {"id": item["id"], "table": "projects", "title": item["title"]}

    # Search people
    people_result = supabase.table("people").select("id, name").not_.is_("follow_up_date", "null").execute()
    for item in (people_result.data or []):
        if search_lower in item["name"].lower():
            return {"id": item["id"], "table": "people", "title": item["name"]}

    return None


def delete_item(inbox_log_id: str) -> bool:
    """
    Delete an item completely - both from target table and inbox_log.
    Used when a capture was a mistake (should have been an update).
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get the inbox_log record to find target
        result = supabase.table("inbox_log").select("*").eq("id", inbox_log_id).execute()
        if not result.data:
            logger.error(f"Could not find inbox_log record: {inbox_log_id}")
            return False

        inbox_record = result.data[0]
        target_table = inbox_record.get("target_table")
        target_id = inbox_record.get("target_id")

        # Delete from target table if it was routed
        if target_table and target_id and target_table != "inbox_log":
            supabase.table(target_table).delete().eq("id", target_id).execute()
            logger.info(f"Deleted from {target_table}: {target_id}")

        # Delete the inbox_log entry
        supabase.table("inbox_log").delete().eq("id", inbox_log_id).execute()
        logger.info(f"Deleted inbox_log: {inbox_log_id}")

        return True

    except Exception as e:
        logger.error(f"Error deleting item: {e}")
        return False


def delete_task(table: str, task_id: str) -> bool:
    """
    Delete a task completely from its table.
    Different from mark_task_done which just updates status.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Deleting task: table={table}, id={task_id}")

        if table not in ["admin", "projects", "people", "ideas"]:
            logger.error(f"Unknown table: {table}")
            return False

        result = supabase.table(table).delete().eq("id", task_id).execute()

        if result.data:
            logger.info(f"Successfully deleted: {result.data}")
            return True
        else:
            logger.warning(f"No rows deleted for table={table}, id={task_id}")
            return False

    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        return False


def reclassify_item(inbox_log_id: str, new_category: str) -> dict:
    """
    Move an item from its current category to a new one.
    Returns the updated inbox_log record.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Get the current inbox_log record
    result = supabase.table("inbox_log").select("*").eq("id", inbox_log_id).execute()
    if not result.data:
        logger.error(f"Could not find inbox_log record: {inbox_log_id}")
        return None

    inbox_record = result.data[0]
    old_table = inbox_record.get("target_table")
    old_id = inbox_record.get("target_id")

    logger.info(f"Reclassifying {inbox_log_id} from {inbox_record.get('category')} to {new_category}")

    # Delete from old category table if it was routed
    if old_table and old_id and old_table != "inbox_log":
        supabase.table(old_table).delete().eq("id", old_id).execute()
        logger.info(f"Deleted from old table: {old_table}")

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
    new_id = new_record.get("id") if new_record else None
    logger.info(f"Routed to {new_table}, new_id: {new_id}")

    # Update inbox_log with new category and target - MUST mark as processed
    update_result = supabase.table("inbox_log").update({
        "category": new_category,
        "confidence": "1.0",
        "processed": True,
        "target_table": new_table,
        "target_id": new_id,
    }).eq("id", inbox_log_id).execute()

    logger.info(f"Update result: {update_result.data}")

    # Return updated inbox record
    inbox_record["category"] = new_category
    inbox_record["target_table"] = new_table
    inbox_record["processed"] = True
    return inbox_record
