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
