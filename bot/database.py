"""Supabase database operations for Second Brain."""

from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def log_to_inbox(raw_message: str, source: str, classification: dict, user_id: int) -> dict:
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
        "user_id": user_id,
    }

    result = supabase.table("inbox_log").insert(data).execute()
    return result.data[0] if result.data else None


def _sanitize_date(value):
    """Convert string 'null' to actual None for date fields."""
    if value is None or value == "null" or value == "":
        return None
    return value


def insert_person(classification: dict, inbox_log_id: str, user_id: int) -> dict:
    """Insert a record into the people table."""
    data = {
        "name": classification.get("title"),
        "notes": classification.get("summary"),
        "follow_up_reason": classification.get("follow_up"),
        "follow_up_date": _sanitize_date(classification.get("follow_up_date")),
        "inbox_log_id": inbox_log_id,
        "status": "active",
        "user_id": user_id,
    }

    result = supabase.table("people").insert(data).execute()
    return result.data[0] if result.data else None


def insert_project(classification: dict, inbox_log_id: str, user_id: int) -> dict:
    """Insert a record into the projects table."""
    data = {
        "title": classification.get("title"),
        "description": classification.get("summary"),
        "next_action": classification.get("next_action"),
        "due_date": _sanitize_date(classification.get("due_date")),
        "status": "active",
        "priority": "medium",
        "inbox_log_id": inbox_log_id,
        "user_id": user_id,
    }

    result = supabase.table("projects").insert(data).execute()
    return result.data[0] if result.data else None


def insert_idea(classification: dict, inbox_log_id: str, user_id: int) -> dict:
    """Insert a record into the ideas table."""
    data = {
        "title": classification.get("title"),
        "content": classification.get("summary"),
        "status": "captured",
        "inbox_log_id": inbox_log_id,
        "user_id": user_id,
    }

    result = supabase.table("ideas").insert(data).execute()
    return result.data[0] if result.data else None


def insert_admin(classification: dict, inbox_log_id: str, user_id: int) -> dict:
    """Insert a record into the admin table."""
    data = {
        "title": classification.get("title"),
        "description": classification.get("summary"),
        "due_date": _sanitize_date(classification.get("due_date")),
        "status": "active",
        "priority": "medium",
        "inbox_log_id": inbox_log_id,
        "user_id": user_id,
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


def route_to_category(classification: dict, inbox_log_id: str, user_id: int) -> tuple:
    """
    Route classification to appropriate table.
    Returns (target_table, target_record).
    """
    category = classification.get("category")

    if category == "people":
        record = insert_person(classification, inbox_log_id, user_id)
        return ("people", record)

    elif category == "projects":
        record = insert_project(classification, inbox_log_id, user_id)
        return ("projects", record)

    elif category == "ideas":
        record = insert_idea(classification, inbox_log_id, user_id)
        return ("ideas", record)

    elif category == "admin":
        record = insert_admin(classification, inbox_log_id, user_id)
        return ("admin", record)

    else:  # needs_review or unknown
        return ("inbox_log", None)


def get_active_projects(user_id: int, limit: int = 5) -> list:
    """Get active projects with their next actions for this user."""
    result = supabase.table("projects").select(
        "title, next_action, due_date, priority"
    ).eq("status", "active").eq("user_id", user_id).order(
        "due_date", desc=False
    ).limit(limit).execute()
    return result.data if result.data else []


def get_follow_ups(user_id: int) -> list:
    """Get people needing follow-up (today or overdue) for this user."""
    from datetime import date
    today = date.today().isoformat()
    result = supabase.table("people").select(
        "name, follow_up_reason, follow_up_date, priority"
    ).eq("status", "active").eq("user_id", user_id).lte("follow_up_date", today).order(
        "follow_up_date", desc=False
    ).execute()
    return result.data if result.data else []


def get_pending_admin(user_id: int, limit: int = 5) -> list:
    """Get active admin tasks for this user."""
    result = supabase.table("admin").select(
        "title, description, due_date, priority"
    ).eq("status", "active").eq("user_id", user_id).order(
        "due_date", desc=False
    ).limit(limit).execute()
    return result.data if result.data else []


def get_high_priority_items(user_id: int) -> dict:
    """Get all high priority active items across buckets for this user."""
    results = {
        "admin": [],
        "projects": [],
        "people": [],
        "ideas": []
    }

    admin_result = supabase.table("admin").select(
        "id, title, due_date"
    ).eq("status", "active").eq("priority", "high").eq("user_id", user_id).limit(10).execute()
    results["admin"] = admin_result.data or []

    projects_result = supabase.table("projects").select(
        "id, title, next_action, due_date"
    ).eq("status", "active").eq("priority", "high").eq("user_id", user_id).limit(10).execute()
    results["projects"] = projects_result.data or []

    people_result = supabase.table("people").select(
        "id, name, follow_up_date"
    ).eq("status", "active").eq("priority", "high").eq("user_id", user_id).limit(10).execute()
    results["people"] = people_result.data or []

    ideas_result = supabase.table("ideas").select(
        "id, title"
    ).eq("status", "active").eq("priority", "high").eq("user_id", user_id).limit(10).execute()
    results["ideas"] = ideas_result.data or []

    return results


def get_random_idea(user_id: int) -> dict:
    """Get a random idea for the 'spark' section for this user."""
    # Supabase doesn't have RANDOM() in the client, so we fetch a few and pick one
    result = supabase.table("ideas").select("title, content").eq("user_id", user_id).limit(10).execute()
    if result.data:
        import random
        return random.choice(result.data)
    return None


def get_needs_review(user_id: int, limit: int = 5) -> list:
    """Get items needing manual review for this user."""
    result = supabase.table("inbox_log").select(
        "id, ai_title, raw_message, confidence, created_at"
    ).eq("category", "needs_review").eq(
        "processed", False
    ).eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
    return result.data if result.data else []


def get_first_needs_review(user_id: int) -> dict:
    """Get the first item needing review for this user."""
    result = supabase.table("inbox_log").select(
        "id, ai_title, raw_message, confidence, created_at"
    ).eq("category", "needs_review").eq(
        "processed", False
    ).eq("user_id", user_id).order("created_at", desc=False).limit(1).execute()
    return result.data[0] if result.data else None


def get_all_active_items(user_id: int) -> dict:
    """Get all active (non-completed/someday) items from each bucket for this user."""
    results = {
        "admin": [],
        "projects": [],
        "people": [],
        "ideas": []
    }

    # Admin: active only, sorted by due_date (nearest first, nulls last)
    admin_result = supabase.table("admin").select(
        "id, title, description, due_date, status, priority"
    ).eq("status", "active").eq("user_id", user_id).order("due_date", desc=False, nullsfirst=False).limit(20).execute()
    results["admin"] = admin_result.data or []

    # Projects: active or paused (not completed/someday)
    projects_result = supabase.table("projects").select(
        "id, title, description, next_action, due_date, status, priority"
    ).in_("status", ["active", "paused"]).eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()
    results["projects"] = projects_result.data or []

    # People: active only (not completed/someday)
    people_result = supabase.table("people").select(
        "id, name, notes, follow_up_reason, follow_up_date, status, priority"
    ).eq("status", "active").eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()
    results["people"] = people_result.data or []

    # Ideas: active only (not archived/someday)
    ideas_result = supabase.table("ideas").select(
        "id, title, content, status, priority"
    ).eq("status", "active").eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()
    results["ideas"] = ideas_result.data or []

    return results


def get_someday_items(user_id: int) -> dict:
    """Get all items with 'someday' status from each bucket for this user."""
    results = {
        "admin": [],
        "projects": [],
        "people": [],
        "ideas": []
    }

    admin_result = supabase.table("admin").select(
        "id, title, description, due_date, status, priority"
    ).eq("status", "someday").eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()
    results["admin"] = admin_result.data or []

    projects_result = supabase.table("projects").select(
        "id, title, description, next_action, due_date, status, priority"
    ).eq("status", "someday").eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()
    results["projects"] = projects_result.data or []

    people_result = supabase.table("people").select(
        "id, name, notes, follow_up_reason, follow_up_date, status, priority"
    ).eq("status", "someday").eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()
    results["people"] = people_result.data or []

    ideas_result = supabase.table("ideas").select(
        "id, title, content, status, priority"
    ).eq("status", "someday").eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()
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


def mark_task_done(table: str, task_id: str, user_id: int = None) -> dict:
    """
    Mark a task as done in the appropriate table.
    Returns dict with 'success' bool and optionally 'next_occurrence' info for recurring tasks.
    For backwards compatibility, also returns True/False when called in boolean context.
    If user_id is provided, filters by it for security.
    """
    import logging
    logger = logging.getLogger(__name__)

    result_info = {"success": False, "next_occurrence": None}

    try:
        logger.info(f"Marking task done: table={table}, id={task_id}")

        # First, get the item to check if it's recurring
        query = supabase.table(table).select("*").eq("id", task_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        item_result = query.execute()
        if not item_result.data:
            logger.warning(f"Item not found: {table}/{task_id}")
            return result_info

        item = item_result.data[0]
        is_recurring = item.get("is_recurring", False)
        recurrence_pattern = item.get("recurrence_pattern")

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
            return result_info

        # Check if any rows were actually updated
        if result.data:
            logger.info(f"Successfully marked done: {result.data}")
            result_info["success"] = True

            # Handle recurring task: create next occurrence
            if is_recurring and recurrence_pattern and table != "ideas":
                logger.info(f"Task is recurring with pattern: {recurrence_pattern}")
                next_date = calculate_next_occurrence(recurrence_pattern)
                new_task = create_recurring_task_copy(table, item, next_date)
                if new_task:
                    result_info["next_occurrence"] = {
                        "date": next_date,
                        "title": new_task.get("title") or new_task.get("name"),
                        "id": new_task.get("id")
                    }
                    logger.info(f"Created next occurrence for {next_date}")
        else:
            logger.warning(f"No rows affected for table={table}, id={task_id}")

        return result_info

    except Exception as e:
        logger.error(f"Error marking task done: {e}")
        return result_info


def update_item_status(table: str, item_id: str, new_status: str, user_id: int = None) -> dict:
    """Update an item's status. Returns the updated item or None on failure.
    If user_id is provided, filters by it for security."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Updating status: table={table}, id={item_id}, new_status={new_status}")
        query = supabase.table(table).update({"status": new_status}).eq("id", item_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()

        if result.data:
            logger.info(f"Successfully updated status: {result.data}")
            return result.data[0]
        else:
            logger.warning(f"No rows affected for table={table}, id={item_id}")
            return None

    except Exception as e:
        logger.error(f"Error updating status: {e}")
        return None


def toggle_item_priority(table: str, item_id: str, user_id: int = None) -> dict:
    """Toggle an item's priority between 'normal' and 'high'. Returns updated item.
    If user_id is provided, filters by it for security."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        # First get current priority
        query = supabase.table(table).select("id, priority").eq("id", item_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()
        if not result.data:
            return None

        current = result.data[0].get("priority", "normal")
        new_priority = "normal" if current == "high" else "high"

        logger.info(f"Toggling priority: {table}/{item_id} from {current} to {new_priority}")
        update_query = supabase.table(table).update({"priority": new_priority}).eq("id", item_id)
        if user_id is not None:
            update_query = update_query.eq("user_id", user_id)
        result = update_query.execute()

        if result.data:
            return result.data[0]
        return None

    except Exception as e:
        logger.error(f"Error toggling priority: {e}")
        return None


def get_item_by_id(table: str, item_id: str, user_id: int = None) -> dict:
    """Get an item by its ID. Optionally filter by user_id for security. Returns the item dict or None."""
    try:
        query = supabase.table(table).select("*").eq("id", item_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()
        if result.data:
            return result.data[0]
        return None
    except Exception:
        return None


def update_item_date(table: str, item_id: str, date_value: str, user_id: int = None) -> dict:
    """Update an item's date field. Returns updated item or None.
    If user_id is provided, filters by it for security."""
    import logging
    logger = logging.getLogger(__name__)

    # Determine which date field to use
    date_field = "follow_up_date" if table == "people" else "due_date"

    try:
        logger.info(f"Setting {date_field} for {table}/{item_id} to {date_value}")
        query = supabase.table(table).update({date_field: date_value}).eq("id", item_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error updating date: {e}")
        return None


def find_item_for_status_change(search_term: str, user_id: int, table_hint: str = None) -> dict:
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
            result = supabase.table(table).select("id, " + title_field + ", status").eq("user_id", user_id).execute()

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


def find_item_for_deletion(search_term: str, user_id: int, table_hint: str = None) -> dict:
    """
    Search for an item to delete across tables for this user.
    If table_hint is provided, only search that table.
    Returns {"id": ..., "table": ..., "title": ...} or None.
    """
    search_lower = search_term.lower()
    tables_to_search = [table_hint] if table_hint else ["admin", "projects", "people", "ideas"]

    for table in tables_to_search:
        if table == "admin":
            result = supabase.table("admin").select("id, title").eq("user_id", user_id).execute()
            for item in (result.data or []):
                if search_lower in item["title"].lower():
                    return {"id": item["id"], "table": "admin", "title": item["title"]}

        elif table == "projects":
            result = supabase.table("projects").select("id, title").eq("user_id", user_id).execute()
            for item in (result.data or []):
                if search_lower in item["title"].lower():
                    return {"id": item["id"], "table": "projects", "title": item["title"]}

        elif table == "people":
            result = supabase.table("people").select("id, name").eq("user_id", user_id).execute()
            for item in (result.data or []):
                if search_lower in item["name"].lower():
                    return {"id": item["id"], "table": "people", "title": item["name"]}

        elif table == "ideas":
            result = supabase.table("ideas").select("id, title").eq("user_id", user_id).execute()
            for item in (result.data or []):
                if search_lower in item["title"].lower():
                    return {"id": item["id"], "table": "ideas", "title": item["title"]}

    return None


def find_task_by_title(search_term: str, user_id: int) -> dict:
    """Fuzzy search for a task by title across all tables for this user."""
    search_lower = search_term.lower()

    # Search admin tasks
    admin_result = supabase.table("admin").select("id, title").eq("status", "pending").eq("user_id", user_id).execute()
    for item in (admin_result.data or []):
        if search_lower in item["title"].lower():
            return {"id": item["id"], "table": "admin", "title": item["title"]}

    # Search projects
    projects_result = supabase.table("projects").select("id, title").eq("status", "active").eq("user_id", user_id).execute()
    for item in (projects_result.data or []):
        if search_lower in item["title"].lower():
            return {"id": item["id"], "table": "projects", "title": item["title"]}

    # Search people
    people_result = supabase.table("people").select("id, name").not_.is_("follow_up_date", "null").eq("user_id", user_id).execute()
    for item in (people_result.data or []):
        if search_lower in item["name"].lower():
            return {"id": item["id"], "table": "people", "title": item["name"]}

    return None


def delete_item(inbox_log_id: str, user_id: int = None) -> bool:
    """
    Delete an item completely - both from target table and inbox_log.
    Used when a capture was a mistake (should have been an update).
    If user_id is provided, filters by it for security.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get the inbox_log record to find target
        query = supabase.table("inbox_log").select("*").eq("id", inbox_log_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()
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


def move_item(source_table: str, item_id: str, dest_table: str, user_id: int = None) -> dict:
    """
    Move an item from one table to another.
    Returns the new record or None on failure.
    If user_id is provided, filters by it for security and includes it in new record.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get the source item
        query = supabase.table(source_table).select("*").eq("id", item_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()

        if not result.data:
            return None
        item = result.data[0]

        if source_table == "people":
            title = item.get("name", "Untitled")
            content = item.get("notes") or item.get("follow_up_reason") or ""
        else:
            title = item.get("title", "Untitled")
            content = item.get("description") or item.get("content") or item.get("notes") or ""

        # Get user_id from source item if not provided
        item_user_id = user_id or item.get("user_id")

        logger.info(f"Moving '{title}' from {source_table} to {dest_table}")

        # Insert into destination table
        new_record = None
        if dest_table == "admin":
            insert_data = {
                "title": title,
                "description": content,
                "status": "pending",
                "priority": "medium",
            }
            if item_user_id:
                insert_data["user_id"] = item_user_id
            new_record = supabase.table("admin").insert(insert_data).execute()
        elif dest_table == "projects":
            insert_data = {
                "title": title,
                "description": content,
                "status": "active",
                "priority": "medium",
            }
            if item_user_id:
                insert_data["user_id"] = item_user_id
            new_record = supabase.table("projects").insert(insert_data).execute()
        elif dest_table == "people":
            insert_data = {
                "name": title,
                "notes": content,
            }
            if item_user_id:
                insert_data["user_id"] = item_user_id
            new_record = supabase.table("people").insert(insert_data).execute()
        elif dest_table == "ideas":
            insert_data = {
                "title": title,
                "content": content,
                "status": "captured",
            }
            if item_user_id:
                insert_data["user_id"] = item_user_id
            new_record = supabase.table("ideas").insert(insert_data).execute()

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


def delete_task(table: str, task_id: str, user_id: int = None) -> bool:
    """
    Delete a task completely from its table.
    Different from mark_task_done which just updates status.
    If user_id is provided, filters by it for security.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Deleting task: table={table}, id={task_id}")

        if table not in ["admin", "projects", "people", "ideas"]:
            logger.error(f"Unknown table: {table}")
            return False

        query = supabase.table(table).delete().eq("id", task_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()

        if result.data:
            logger.info(f"Successfully deleted: {result.data}")
            return True
        else:
            logger.warning(f"No rows deleted for table={table}, id={task_id}")
            return False

    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        return False


def reclassify_item(inbox_log_id: str, new_category: str, user_id: int = None) -> dict:
    """
    Move an item from its current category to a new one.
    Returns the updated inbox_log record.
    If user_id is provided, filters by it for security.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Get the current inbox_log record
    query = supabase.table("inbox_log").select("*").eq("id", inbox_log_id)
    if user_id is not None:
        query = query.eq("user_id", user_id)
    result = query.execute()
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

    # Get user_id from inbox_record if not provided
    item_user_id = user_id or inbox_record.get("user_id")

    # Route to new category
    new_table, new_record = route_to_category(classification, inbox_log_id, item_user_id)
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

def get_setting(key: str, user_id: int = None) -> str:
    """Get a setting value by key. If user_id is provided, gets user-specific setting."""
    query = supabase.table("settings").select("value").eq("key", key)
    if user_id is not None:
        query = query.eq("user_id", user_id)
    result = query.execute()
    return result.data[0]["value"] if result.data else None


def set_setting(key: str, value: str, user_id: int = None) -> bool:
    """Update a setting value. If user_id is provided, sets user-specific setting."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        data = {"key": key, "value": value}
        if user_id is not None:
            data["user_id"] = user_id
        result = supabase.table("settings").upsert(
            data,
            on_conflict="key,user_id" if user_id else "key"
        ).execute()
        logger.info(f"set_setting result: {result.data}")
        return bool(result.data)
    except Exception as e:
        logger.error(f"Error in set_setting: {e}")
        return False


def get_all_settings(user_id: int = None) -> dict:
    """Get all settings as a dictionary. If user_id is provided, gets user-specific settings."""
    query = supabase.table("settings").select("key, value")
    if user_id is not None:
        query = query.eq("user_id", user_id)
    result = query.execute()
    return {row["key"]: row["value"] for row in (result.data or [])}


# ============================================
# Evening Recap Functions
# ============================================

def get_completed_today(user_id: int) -> dict:
    """Get items completed today from admin, projects, people, ideas for this user."""
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
    ).eq("status", "completed").eq("user_id", user_id).gte("completed_at", today_start).execute()
    results["admin"] = admin_result.data or []

    # Projects completed today
    projects_result = supabase.table("projects").select(
        "id, title"
    ).eq("status", "completed").eq("user_id", user_id).gte("completed_at", today_start).execute()
    results["projects"] = projects_result.data or []

    # People follow-ups completed today
    people_result = supabase.table("people").select(
        "id, name"
    ).eq("status", "completed").eq("user_id", user_id).gte("completed_at", today_start).execute()
    results["people"] = people_result.data or []

    # Ideas archived/completed today
    ideas_result = supabase.table("ideas").select(
        "id, title"
    ).eq("status", "archived").eq("user_id", user_id).gte("completed_at", today_start).execute()
    results["ideas"] = ideas_result.data or []

    return results


def get_tomorrow_priorities(user_id: int) -> list:
    """Get items due tomorrow or marked high/urgent priority for this user."""
    from datetime import date, timedelta
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    priorities = []

    # Admin due tomorrow or high/urgent priority
    admin_result = supabase.table("admin").select(
        "id, title, due_date, priority"
    ).in_("status", ["pending", "in_progress"]).eq("user_id", user_id).execute()
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
    ).in_("status", ["active"]).eq("user_id", user_id).execute()
    for item in (projects_result.data or []):
        if item.get("due_date") == tomorrow or item.get("priority") in ["high", "urgent"]:
            priorities.append({
                "table": "projects",
                "title": item["title"],
                "due_date": item.get("due_date"),
                "priority": item.get("priority"),
                "next_action": item.get("next_action")
            })

    # People with follow-up tomorrow or high/urgent priority
    people_result = supabase.table("people").select(
        "id, name, follow_up_date, follow_up_reason, priority"
    ).eq("status", "active").eq("user_id", user_id).execute()
    for item in (people_result.data or []):
        if item.get("follow_up_date") == tomorrow or item.get("priority") in ["high", "urgent"]:
            priorities.append({
                "table": "people",
                "title": item["name"],
                "due_date": item.get("follow_up_date"),
                "priority": item.get("priority"),
                "follow_up_reason": item.get("follow_up_reason")
            })

    return priorities


def get_overdue_items(user_id: int) -> list:
    """Get items where due_date or follow_up_date is before today for this user."""
    from datetime import date
    today = date.today().isoformat()

    overdue = []

    # Overdue admin tasks
    admin_result = supabase.table("admin").select(
        "id, title, due_date"
    ).eq("status", "active").eq("user_id", user_id).lt("due_date", today).execute()
    for item in (admin_result.data or []):
        overdue.append({
            "table": "admin",
            "title": item["title"],
            "due_date": item.get("due_date")
        })

    # Overdue projects
    projects_result = supabase.table("projects").select(
        "id, title, due_date"
    ).in_("status", ["active"]).eq("user_id", user_id).lt("due_date", today).execute()
    for item in (projects_result.data or []):
        overdue.append({
            "table": "projects",
            "title": item["title"],
            "due_date": item.get("due_date")
        })

    # Overdue people follow-ups
    people_result = supabase.table("people").select(
        "id, name, follow_up_date"
    ).eq("status", "active").eq("user_id", user_id).lt("follow_up_date", today).execute()
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


# ============================================
# Weekly Report Functions
# ============================================

def get_completed_this_week(user_id: int) -> dict:
    """Get items completed in the past 7 days from all buckets for this user."""
    from datetime import date, datetime, timedelta
    week_ago = datetime.combine(date.today() - timedelta(days=7), datetime.min.time()).isoformat()

    results = {
        "admin": [],
        "projects": [],
        "people": [],
        "ideas": []
    }

    admin_result = supabase.table("admin").select(
        "id, title"
    ).eq("status", "completed").eq("user_id", user_id).gte("completed_at", week_ago).execute()
    results["admin"] = admin_result.data or []

    projects_result = supabase.table("projects").select(
        "id, title"
    ).eq("status", "completed").eq("user_id", user_id).gte("completed_at", week_ago).execute()
    results["projects"] = projects_result.data or []

    people_result = supabase.table("people").select(
        "id, name"
    ).eq("status", "completed").eq("user_id", user_id).gte("completed_at", week_ago).execute()
    results["people"] = people_result.data or []

    ideas_result = supabase.table("ideas").select(
        "id, title"
    ).eq("status", "archived").eq("user_id", user_id).gte("completed_at", week_ago).execute()
    results["ideas"] = ideas_result.data or []

    return results


def get_random_someday_item(user_id: int) -> dict:
    """Get a random someday item to surface periodically for this user."""
    import random

    all_someday = []

    admin_result = supabase.table("admin").select("id, title").eq("status", "someday").eq("user_id", user_id).limit(10).execute()
    for item in (admin_result.data or []):
        all_someday.append({"table": "admin", "title": item["title"]})

    projects_result = supabase.table("projects").select("id, title").eq("status", "someday").eq("user_id", user_id).limit(10).execute()
    for item in (projects_result.data or []):
        all_someday.append({"table": "projects", "title": item["title"]})

    ideas_result = supabase.table("ideas").select("id, title").eq("status", "someday").eq("user_id", user_id).limit(10).execute()
    for item in (ideas_result.data or []):
        all_someday.append({"table": "ideas", "title": item["title"]})

    return random.choice(all_someday) if all_someday else None


# ============================================
# Item Editing Functions
# ============================================

def update_item_title(table: str, item_id: str, new_title: str, user_id: int = None) -> dict:
    """Update an item's title (or name for people table). Returns updated item or None.
    If user_id is provided, filters by it for security."""
    import logging
    logger = logging.getLogger(__name__)

    # People table uses 'name', others use 'title'
    title_field = "name" if table == "people" else "title"

    try:
        logger.info(f"Updating {title_field} for {table}/{item_id} to: {new_title}")
        query = supabase.table(table).update({title_field: new_title}).eq("id", item_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error updating title: {e}")
        return None


def update_item_description(table: str, item_id: str, new_description: str, user_id: int = None) -> dict:
    """Update an item's description/content/notes. Returns updated item or None.
    If user_id is provided, filters by it for security."""
    import logging
    logger = logging.getLogger(__name__)

    # Different tables use different field names for description
    if table == "people":
        desc_field = "notes"
    elif table == "ideas":
        desc_field = "content"
    else:  # admin, projects
        desc_field = "description"

    try:
        logger.info(f"Updating {desc_field} for {table}/{item_id}")
        query = supabase.table(table).update({desc_field: new_description}).eq("id", item_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error updating description: {e}")
        return None


# ============================================
# Recurring Tasks Functions
# ============================================

def calculate_next_occurrence(pattern: str, from_date=None) -> str:
    """
    Calculate the next occurrence date based on recurrence pattern.
    Always returns a FUTURE date (never today or past).

    Patterns:
    - daily: Every day
    - weekly:N: Every week on day N (0=Mon, 6=Sun)
    - biweekly:N: Every other week on day N
    - monthly:N: Nth day of each month (1-31)
    - monthly:last: Last day of month
    - monthly:first_mon, first_tue, etc.: First weekday of month
    """
    from datetime import date, timedelta
    import calendar
    import logging
    logger = logging.getLogger(__name__)

    if from_date is None:
        from_date = date.today()
    elif isinstance(from_date, str):
        from datetime import datetime
        from_date = datetime.strptime(from_date, "%Y-%m-%d").date()

    logger.info(f"Calculating next occurrence for pattern '{pattern}' from {from_date}")

    if pattern == "daily":
        # Next day after from_date
        next_date = from_date + timedelta(days=1)

    elif pattern.startswith("weekly:"):
        # weekly:N where N is 0-6 (Mon-Sun)
        target_day = int(pattern.split(":")[1])
        days_ahead = target_day - from_date.weekday()
        if days_ahead <= 0:  # Target day already happened this week or is today
            days_ahead += 7
        next_date = from_date + timedelta(days=days_ahead)

    elif pattern.startswith("biweekly:"):
        # biweekly:N - every other week on day N
        target_day = int(pattern.split(":")[1])
        days_ahead = target_day - from_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_date = from_date + timedelta(days=days_ahead)
        # Add another week to make it biweekly
        if (next_date - from_date).days <= 7:
            next_date += timedelta(days=7)

    elif pattern.startswith("monthly:"):
        spec = pattern.split(":")[1]

        if spec == "last":
            # Last day of next month
            if from_date.month == 12:
                next_month, next_year = 1, from_date.year + 1
            else:
                next_month, next_year = from_date.month + 1, from_date.year
            last_day = calendar.monthrange(next_year, next_month)[1]
            next_date = date(next_year, next_month, last_day)

        elif spec.startswith("first_"):
            # First weekday of month (first_mon, first_tue, etc.)
            weekday_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            target_weekday = weekday_names.index(spec.split("_")[1])
            next_date = _get_nth_weekday_of_month(from_date.year, from_date.month, target_weekday, 1)
            # If already past, get next month's
            if next_date <= from_date:
                if from_date.month == 12:
                    next_month, next_year = 1, from_date.year + 1
                else:
                    next_month, next_year = from_date.month + 1, from_date.year
                next_date = _get_nth_weekday_of_month(next_year, next_month, target_weekday, 1)

        else:
            # Specific day of month (1-31)
            target_day = int(spec)
            next_month = from_date.month
            next_year = from_date.year

            # Check if target day already passed this month
            max_day = calendar.monthrange(next_year, next_month)[1]
            actual_day = min(target_day, max_day)

            if from_date.day >= actual_day:
                # Move to next month
                if next_month == 12:
                    next_month, next_year = 1, next_year + 1
                else:
                    next_month += 1
                max_day = calendar.monthrange(next_year, next_month)[1]
                actual_day = min(target_day, max_day)

            next_date = date(next_year, next_month, actual_day)

    else:
        # Unknown pattern, default to tomorrow
        logger.warning(f"Unknown recurrence pattern: {pattern}")
        next_date = from_date + timedelta(days=1)

    # Ensure we never return today or past
    while next_date <= date.today():
        next_date += timedelta(days=1)

    logger.info(f"Next occurrence: {next_date}")
    return next_date.isoformat()


def _get_nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> 'date':
    """Get the nth occurrence of a weekday in a month (n=1 for first, n=2 for second, etc.)."""
    from datetime import date
    import calendar

    # Find first day of the month
    first_day = date(year, month, 1)
    first_weekday = first_day.weekday()

    # Calculate days until target weekday
    days_until = (weekday - first_weekday) % 7

    # Calculate the nth occurrence
    target_day = 1 + days_until + (n - 1) * 7

    # Make sure we don't exceed month bounds
    max_day = calendar.monthrange(year, month)[1]
    if target_day > max_day:
        return None

    return date(year, month, target_day)


def set_recurrence_pattern(table: str, item_id: str, pattern: str, user_id: int = None) -> dict:
    """Set a recurrence pattern on an item. Returns updated item or None.
    If user_id is provided, filters by it for security."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Setting recurrence pattern '{pattern}' for {table}/{item_id}")
        query = supabase.table(table).update({
            "recurrence_pattern": pattern,
            "is_recurring": True
        }).eq("id", item_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error setting recurrence: {e}")
        return None


def clear_recurrence(table: str, item_id: str, user_id: int = None) -> dict:
    """Clear recurrence from an item. Returns updated item or None.
    If user_id is provided, filters by it for security."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Clearing recurrence for {table}/{item_id}")
        query = supabase.table(table).update({
            "recurrence_pattern": None,
            "is_recurring": False
        }).eq("id", item_id)
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = query.execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error clearing recurrence: {e}")
        return None


def create_recurring_task_copy(table: str, original_item: dict, next_date: str, user_id: int = None) -> dict:
    """Create a new task as a copy of a recurring task with a new due date.
    Uses user_id from original_item if not provided."""
    import logging
    logger = logging.getLogger(__name__)

    # Get user_id from original item if not provided
    item_user_id = user_id or original_item.get("user_id")

    try:
        # Build data for new task based on table type
        if table == "admin":
            data = {
                "title": original_item.get("title"),
                "description": original_item.get("description"),
                "due_date": next_date,
                "status": "active",
                "priority": original_item.get("priority", "normal"),
                "recurrence_pattern": original_item.get("recurrence_pattern"),
                "is_recurring": True,
            }
        elif table == "projects":
            data = {
                "title": original_item.get("title"),
                "description": original_item.get("description"),
                "next_action": original_item.get("next_action"),
                "due_date": next_date,
                "status": "active",
                "priority": original_item.get("priority", "medium"),
                "recurrence_pattern": original_item.get("recurrence_pattern"),
                "is_recurring": True,
            }
        elif table == "people":
            data = {
                "name": original_item.get("name"),
                "notes": original_item.get("notes"),
                "follow_up_reason": original_item.get("follow_up_reason"),
                "follow_up_date": next_date,
                "status": "active",
                "priority": original_item.get("priority", "normal"),
                "recurrence_pattern": original_item.get("recurrence_pattern"),
                "is_recurring": True,
            }
        else:
            logger.error(f"Recurring tasks not supported for table: {table}")
            return None

        # Add user_id to the new task
        if item_user_id:
            data["user_id"] = item_user_id

        logger.info(f"Creating recurring copy in {table} with due date {next_date}")
        result = supabase.table(table).insert(data).execute()
        if result.data:
            logger.info(f"Created recurring copy: {result.data[0]['id']}")
            return result.data[0]
        return None

    except Exception as e:
        logger.error(f"Error creating recurring copy: {e}")
        return None


# ============================================
# Undo functionality
# ============================================

def save_undo_state(user_id: int, action_type: str, table: str, item_id: str, previous_data: dict) -> bool:
    """
    Save the previous state of an item before an action.
    Keeps only the last 10 undo entries per user.
    """
    try:
        import json

        # Insert new undo entry
        data = {
            "user_id": user_id,
            "action_type": action_type,
            "table_name": table,
            "item_id": item_id,
            "previous_data": previous_data,
        }
        supabase.table("undo_log").insert(data).execute()

        # Cleanup: keep only last 10 entries per user
        result = supabase.table("undo_log").select("id").eq(
            "user_id", user_id
        ).order("created_at", desc=True).execute()

        if result.data and len(result.data) > 10:
            old_ids = [r["id"] for r in result.data[10:]]
            for old_id in old_ids:
                supabase.table("undo_log").delete().eq("id", old_id).execute()

        return True
    except Exception as e:
        logger.error(f"Error saving undo state: {e}")
        return False


def get_last_undo(user_id: int) -> dict:
    """Get the most recent undo entry for a user."""
    try:
        result = supabase.table("undo_log").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).limit(1).execute()

        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error getting last undo: {e}")
        return None


def execute_undo(user_id: int) -> dict:
    """
    Execute undo for the last action.
    Returns {"success": bool, "message": str, "table": str}
    """
    try:
        undo_entry = get_last_undo(user_id)
        if not undo_entry:
            return {"success": False, "message": "Nothing to undo"}

        action_type = undo_entry["action_type"]
        table = undo_entry["table_name"]
        item_id = undo_entry["item_id"]
        previous_data = undo_entry["previous_data"]

        # Execute undo based on action type
        if action_type == "complete":
            # Restore to active status
            supabase.table(table).update({
                "status": previous_data.get("status", "active"),
                "completed_at": None
            }).eq("id", item_id).execute()
            message = f"Restored '{previous_data.get('title') or previous_data.get('name')}' to active"

        elif action_type == "delete":
            # Re-insert the deleted item
            # Remove id and timestamps that will be auto-generated
            insert_data = {k: v for k, v in previous_data.items()
                         if k not in ['id', 'created_at', 'updated_at', 'completed_at']}
            insert_data['id'] = item_id  # Keep same ID
            supabase.table(table).insert(insert_data).execute()
            message = f"Restored deleted '{previous_data.get('title') or previous_data.get('name')}'"

        elif action_type == "priority":
            # Restore previous priority
            supabase.table(table).update({
                "priority": previous_data.get("priority", "normal")
            }).eq("id", item_id).execute()
            message = f"Priority restored to {previous_data.get('priority', 'normal')}"

        elif action_type == "date":
            # Restore previous date
            date_field = "follow_up_date" if table == "people" else "due_date"
            supabase.table(table).update({
                date_field: previous_data.get(date_field)
            }).eq("id", item_id).execute()
            message = "Date restored"

        elif action_type == "status":
            # Restore previous status (someday, paused, active)
            supabase.table(table).update({
                "status": previous_data.get("status")
            }).eq("id", item_id).execute()
            message = f"Status restored to {previous_data.get('status')}"

        elif action_type == "move":
            # Move back to original table - complex, just restore status for now
            message = "Move undo not fully supported - item may need manual adjustment"

        else:
            return {"success": False, "message": f"Unknown action type: {action_type}"}

        # Delete the undo entry after executing
        supabase.table("undo_log").delete().eq("id", undo_entry["id"]).execute()

        return {"success": True, "message": message, "table": table}

    except Exception as e:
        logger.error(f"Error executing undo: {e}")
        return {"success": False, "message": f"Undo failed: {str(e)}"}


# --- User Management Functions ---

def get_user(telegram_id: int) -> dict:
    """Get a user by Telegram ID. Returns user dict or None."""
    try:
        result = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error getting user {telegram_id}: {e}")
        return None


def is_user_authorized(telegram_id: int) -> bool:
    """Check if a Telegram user is authorized (exists and active)."""
    user = get_user(telegram_id)
    return user is not None and user.get("is_active", False)


def is_user_admin(telegram_id: int) -> bool:
    """Check if a Telegram user is an admin."""
    user = get_user(telegram_id)
    return user is not None and user.get("is_admin", False) and user.get("is_active", False)


def add_user(telegram_id: int, name: str = None, added_by: int = None) -> dict:
    """Add a new user to the users table. Returns the created user or None."""
    try:
        # Check if user already exists
        existing = get_user(telegram_id)
        if existing:
            if not existing.get("is_active"):
                # Reactivate deactivated user
                result = supabase.table("users").update({
                    "is_active": True,
                    "name": name or existing.get("name"),
                }).eq("telegram_id", telegram_id).execute()
                return result.data[0] if result.data else None
            return existing

        data = {
            "telegram_id": telegram_id,
            "name": name,
            "added_by": added_by,
            "is_admin": False,
            "is_active": True,
        }
        result = supabase.table("users").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error adding user {telegram_id}: {e}")
        return None


def list_users() -> list:
    """List all users (active and inactive)."""
    try:
        result = supabase.table("users").select("*").order("created_at").execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return []


def deactivate_user(telegram_id: int) -> bool:
    """Deactivate a user (set is_active=False). Returns True on success."""
    try:
        result = supabase.table("users").update({"is_active": False}).eq("telegram_id", telegram_id).execute()
        return len(result.data) > 0 if result.data else False
    except Exception as e:
        logger.error(f"Error deactivating user {telegram_id}: {e}")
        return False


def get_all_active_user_ids() -> list:
    """Get all active user Telegram IDs. Used by cron jobs."""
    try:
        result = supabase.table("users").select("telegram_id").eq("is_active", True).execute()
        return [row["telegram_id"] for row in result.data] if result.data else []
    except Exception as e:
        logger.error(f"Error getting active user IDs: {e}")
        return []
