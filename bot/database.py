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


def _sanitize_date(value):
    """Convert string 'null' to actual None for date fields."""
    if value is None or value == "null" or value == "":
        return None
    return value


def insert_person(classification: dict, inbox_log_id: str) -> dict:
    """Insert a record into the people table."""
    data = {
        "name": classification.get("title"),
        "notes": classification.get("summary"),
        "follow_up_reason": classification.get("follow_up"),
        "follow_up_date": _sanitize_date(classification.get("follow_up_date")),
        "inbox_log_id": inbox_log_id,
        "status": "active",
    }

    result = supabase.table("people").insert(data).execute()
    return result.data[0] if result.data else None


def insert_project(classification: dict, inbox_log_id: str) -> dict:
    """Insert a record into the projects table."""
    data = {
        "title": classification.get("title"),
        "description": classification.get("summary"),
        "next_action": classification.get("next_action"),
        "due_date": _sanitize_date(classification.get("due_date")),
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
        "due_date": _sanitize_date(classification.get("due_date")),
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


def get_all_active_items() -> dict:
    """Get all active (non-completed) items from each bucket."""
    results = {
        "admin": [],
        "projects": [],
        "people": [],
        "ideas": []
    }

    # Admin: pending or in_progress, sorted by due_date (nearest first, nulls last)
    admin_result = supabase.table("admin").select(
        "id, title, description, due_date, status"
    ).in_("status", ["pending", "in_progress"]).order("due_date", desc=False, nullsfirst=False).limit(20).execute()
    results["admin"] = admin_result.data or []

    # Projects: active or paused (not completed/archived)
    projects_result = supabase.table("projects").select(
        "id, title, description, next_action, due_date, status"
    ).in_("status", ["active", "paused"]).order("created_at", desc=True).limit(20).execute()
    results["projects"] = projects_result.data or []

    # People: active only (not completed)
    people_result = supabase.table("people").select(
        "id, name, notes, follow_up_reason, follow_up_date, status"
    ).eq("status", "active").order("created_at", desc=True).limit(20).execute()
    results["people"] = people_result.data or []

    # Ideas: captured or exploring (not archived)
    ideas_result = supabase.table("ideas").select(
        "id, title, content, status"
    ).in_("status", ["captured", "exploring", "actionable"]).order("created_at", desc=True).limit(20).execute()
    results["ideas"] = ideas_result.data or []

    return results


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

        from datetime import datetime
        now = datetime.utcnow().isoformat()

        if table == "admin":
            result = supabase.table("admin").update({"status": "completed", "completed_at": now}).eq("id", task_id).execute()
            logger.info(f"Admin update result: {result.data}")
        elif table == "projects":
            result = supabase.table("projects").update({"status": "completed", "completed_at": now}).eq("id", task_id).execute()
            logger.info(f"Projects update result: {result.data}")
        elif table == "people":
            result = supabase.table("people").update({"status": "completed", "completed_at": now}).eq("id", task_id).execute()
            logger.info(f"People update result: {result.data}")
        elif table == "ideas":
            result = supabase.table("ideas").update({"status": "archived", "completed_at": now}).eq("id", task_id).execute()
            logger.info(f"Ideas update result: {result.data}")
        else:
            logger.error(f"Unknown table: {table}")
            return False

        # Check if any rows were actually updated/deleted
        if result.data:
            logger.info(f"Successfully marked done: {result.data}")
            return True
        else:
            logger.warning(f"No rows affected for table={table}, id={task_id}")
            return False

    except Exception as e:
        logger.error(f"Error marking task done: {e}")
        return False


def update_item_status(table: str, item_id: str, new_status: str) -> dict:
    """Update an item's status. Returns the updated item or None on failure."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Updating status: table={table}, id={item_id}, new_status={new_status}")
        result = supabase.table(table).update({"status": new_status}).eq("id", item_id).execute()

        if result.data:
            logger.info(f"Successfully updated status: {result.data}")
            return result.data[0]
        else:
            logger.warning(f"No rows affected for table={table}, id={item_id}")
            return None

    except Exception as e:
        logger.error(f"Error updating status: {e}")
        return None


def find_item_for_status_change(search_term: str, table_hint: str = None) -> dict:
    """Find an item by title/name for status change. Returns item with table info or None."""
    import logging
    logger = logging.getLogger(__name__)

    search_lower = search_term.lower().strip()
    logger.info(f"Searching for item to change status: '{search_term}' (table hint: {table_hint})")

    # If table hint provided, search only that table
    tables_to_search = [table_hint] if table_hint else ["projects", "admin", "ideas", "people"]

    for table in tables_to_search:
        try:
            title_field = "name" if table == "people" else "title"
            result = supabase.table(table).select("id, " + title_field + ", status").execute()

            for item in (result.data or []):
                item_title = (item.get(title_field) or "").lower()
                if search_lower in item_title or item_title in search_lower:
                    return {
                        "id": item["id"],
                        "table": table,
                        "title": item.get(title_field),
                        "status": item.get("status")
                    }
        except Exception as e:
            logger.error(f"Error searching {table}: {e}")

    return None


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


def move_item(source_table: str, item_id: str, dest_table: str) -> dict:
    """
    Move an item from one table to another.
    Returns the new record or None on failure.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get the source item
        if source_table == "people":
            result = supabase.table(source_table).select("*").eq("id", item_id).execute()
            if not result.data:
                return None
            item = result.data[0]
            title = item.get("name", "Untitled")
            content = item.get("notes") or item.get("follow_up_reason") or ""
        else:
            result = supabase.table(source_table).select("*").eq("id", item_id).execute()
            if not result.data:
                return None
            item = result.data[0]
            title = item.get("title", "Untitled")
            content = item.get("description") or item.get("content") or item.get("notes") or ""

        logger.info(f"Moving '{title}' from {source_table} to {dest_table}")

        # Insert into destination table
        new_record = None
        if dest_table == "admin":
            new_record = supabase.table("admin").insert({
                "title": title,
                "description": content,
                "status": "pending",
                "priority": "medium",
            }).execute()
        elif dest_table == "projects":
            new_record = supabase.table("projects").insert({
                "title": title,
                "description": content,
                "status": "active",
                "priority": "medium",
            }).execute()
        elif dest_table == "people":
            new_record = supabase.table("people").insert({
                "name": title,
                "notes": content,
            }).execute()
        elif dest_table == "ideas":
            new_record = supabase.table("ideas").insert({
                "title": title,
                "content": content,
                "status": "captured",
            }).execute()

        if not new_record or not new_record.data:
            logger.error(f"Failed to insert into {dest_table}")
            return None

        # Delete from source table
        supabase.table(source_table).delete().eq("id", item_id).execute()
        logger.info(f"Moved successfully, new id: {new_record.data[0]['id']}")

        return {"title": title, "table": dest_table, "id": new_record.data[0]["id"]}

    except Exception as e:
        logger.error(f"Error moving item: {e}")
        return None


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


# ============================================
# Settings Functions
# ============================================

def get_setting(key: str) -> str:
    """Get a setting value by key."""
    result = supabase.table("settings").select("value").eq("key", key).execute()
    return result.data[0]["value"] if result.data else None


def set_setting(key: str, value: str) -> bool:
    """Update a setting value."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        result = supabase.table("settings").upsert(
            {"key": key, "value": value},
            on_conflict="key"
        ).execute()
        logger.info(f"set_setting result: {result.data}")
        return bool(result.data)
    except Exception as e:
        logger.error(f"Error in set_setting: {e}")
        return False


def get_all_settings() -> dict:
    """Get all settings as a dictionary."""
    result = supabase.table("settings").select("key, value").execute()
    return {row["key"]: row["value"] for row in (result.data or [])}


# ============================================
# Evening Recap Functions
# ============================================

def get_completed_today() -> dict:
    """Get items completed today from admin, projects, people, ideas."""
    from datetime import date, datetime
    today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()

    results = {
        "admin": [],
        "projects": [],
        "people": [],
        "ideas": []
    }

    # Admin completed today
    admin_result = supabase.table("admin").select(
        "id, title"
    ).eq("status", "completed").gte("completed_at", today_start).execute()
    results["admin"] = admin_result.data or []

    # Projects completed today
    projects_result = supabase.table("projects").select(
        "id, title"
    ).eq("status", "completed").gte("completed_at", today_start).execute()
    results["projects"] = projects_result.data or []

    # People follow-ups completed today
    people_result = supabase.table("people").select(
        "id, name"
    ).eq("status", "completed").gte("completed_at", today_start).execute()
    results["people"] = people_result.data or []

    # Ideas archived/completed today
    ideas_result = supabase.table("ideas").select(
        "id, title"
    ).eq("status", "archived").gte("completed_at", today_start).execute()
    results["ideas"] = ideas_result.data or []

    return results


def get_tomorrow_priorities() -> list:
    """Get items due tomorrow or marked high/urgent priority."""
    from datetime import date, timedelta
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    priorities = []

    # Admin due tomorrow or high/urgent priority
    admin_result = supabase.table("admin").select(
        "id, title, due_date, priority"
    ).in_("status", ["pending", "in_progress"]).execute()
    for item in (admin_result.data or []):
        if item.get("due_date") == tomorrow or item.get("priority") in ["high", "urgent"]:
            priorities.append({
                "table": "admin",
                "title": item["title"],
                "due_date": item.get("due_date"),
                "priority": item.get("priority")
            })

    # Projects due tomorrow or high/urgent priority
    projects_result = supabase.table("projects").select(
        "id, title, due_date, priority, next_action"
    ).in_("status", ["active"]).execute()
    for item in (projects_result.data or []):
        if item.get("due_date") == tomorrow or item.get("priority") in ["high", "urgent"]:
            priorities.append({
                "table": "projects",
                "title": item["title"],
                "due_date": item.get("due_date"),
                "priority": item.get("priority"),
                "next_action": item.get("next_action")
            })

    return priorities


def get_overdue_items() -> list:
    """Get items where due_date or follow_up_date is before today."""
    from datetime import date
    today = date.today().isoformat()

    overdue = []

    # Overdue admin tasks
    admin_result = supabase.table("admin").select(
        "id, title, due_date"
    ).in_("status", ["pending", "in_progress"]).lt("due_date", today).execute()
    for item in (admin_result.data or []):
        overdue.append({
            "table": "admin",
            "title": item["title"],
            "due_date": item.get("due_date")
        })

    # Overdue projects
    projects_result = supabase.table("projects").select(
        "id, title, due_date"
    ).in_("status", ["active"]).lt("due_date", today).execute()
    for item in (projects_result.data or []):
        overdue.append({
            "table": "projects",
            "title": item["title"],
            "due_date": item.get("due_date")
        })

    # Overdue people follow-ups
    people_result = supabase.table("people").select(
        "id, name, follow_up_date"
    ).eq("status", "active").lt("follow_up_date", today).execute()
    for item in (people_result.data or []):
        overdue.append({
            "table": "people",
            "title": item["name"],
            "due_date": item.get("follow_up_date")
        })

    return overdue


# ============================================
# Reminder Functions
# ============================================

def create_reminder(target_table: str, target_id: str, title: str, recurrence: str,
                    next_reminder_at: str, recurrence_day: int = None) -> dict:
    """Create a new reminder."""
    data = {
        "target_table": target_table,
        "target_id": target_id,
        "title": title,
        "recurrence": recurrence,
        "next_reminder_at": next_reminder_at,
        "recurrence_day": recurrence_day,
        "active": True
    }
    result = supabase.table("reminders").insert(data).execute()
    return result.data[0] if result.data else None


def get_due_reminders() -> list:
    """Get all active reminders where next_reminder_at <= today."""
    from datetime import date
    today = date.today().isoformat()
    result = supabase.table("reminders").select("*").eq("active", True).lte("next_reminder_at", today).execute()
    return result.data or []


def update_reminder_sent(reminder_id: str, recurrence: str, recurrence_day: int = None) -> bool:
    """Update last_sent_at and calculate next occurrence."""
    from datetime import date, timedelta, datetime

    today = date.today()
    now = datetime.utcnow().isoformat()

    # Calculate next reminder date based on recurrence
    if recurrence == "daily":
        next_date = today + timedelta(days=1)
    elif recurrence == "weekly":
        # Next occurrence is 7 days from now, or specific day of week
        if recurrence_day is not None:
            days_ahead = recurrence_day - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_date = today + timedelta(days=days_ahead)
        else:
            next_date = today + timedelta(days=7)
    elif recurrence == "monthly":
        # Next occurrence on same day next month
        if recurrence_day:
            target_day = recurrence_day
        else:
            target_day = today.day

        # Move to next month
        if today.month == 12:
            next_month = 1
            next_year = today.year + 1
        else:
            next_month = today.month + 1
            next_year = today.year

        # Handle months with fewer days
        import calendar
        max_day = calendar.monthrange(next_year, next_month)[1]
        target_day = min(target_day, max_day)
        next_date = date(next_year, next_month, target_day)
    else:
        next_date = today + timedelta(days=1)

    result = supabase.table("reminders").update({
        "last_sent_at": now,
        "next_reminder_at": next_date.isoformat()
    }).eq("id", reminder_id).execute()

    return bool(result.data)


def deactivate_reminder(reminder_id: str) -> bool:
    """Deactivate a reminder."""
    result = supabase.table("reminders").update({"active": False}).eq("id", reminder_id).execute()
    return bool(result.data)
