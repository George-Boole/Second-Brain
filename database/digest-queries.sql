-- Second Brain Daily Digest Queries
-- These queries are used by Make.com to gather data for the morning summary

-- 1. Active Projects and their next actions
SELECT title, next_action, due_date 
FROM projects 
WHERE status = 'active' 
ORDER BY priority DESC, due_date ASC 
LIMIT 5;

-- 2. People to follow up with
SELECT name, follow_up_reason, follow_up_date 
FROM people 
WHERE follow_up_date <= CURRENT_DATE 
ORDER BY follow_up_date ASC;

-- 3. Pending admin tasks
SELECT title, description, due_date 
FROM admin 
WHERE status = 'pending' 
ORDER BY due_date ASC 
LIMIT 5;

-- 4. Random Idea (The "Spark")
SELECT title, content
FROM ideas
ORDER BY RANDOM()
LIMIT 1;

-- 5. Items Needing Review (unprocessed low-confidence items)
SELECT id, ai_title, raw_message, confidence, created_at
FROM inbox_log
WHERE category = 'needs_review'
  AND processed = false
ORDER BY created_at DESC
LIMIT 5;

-- 6. Weekly Stats (for Sunday review)
SELECT
  COUNT(*) as total_captures,
  COUNT(CASE WHEN category = 'people' THEN 1 END) as people_count,
  COUNT(CASE WHEN category = 'projects' THEN 1 END) as projects_count,
  COUNT(CASE WHEN category = 'ideas' THEN 1 END) as ideas_count,
  COUNT(CASE WHEN category = 'admin' THEN 1 END) as admin_count,
  COUNT(CASE WHEN category = 'needs_review' THEN 1 END) as needs_review_count
FROM inbox_log
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days';
