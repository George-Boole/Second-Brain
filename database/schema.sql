-- Second Brain Database Schema
-- Run this in Supabase SQL Editor
-- Created: 2026-01-23

-- ============================================
-- TABLE 1: inbox_log (Audit Trail)
-- ============================================
-- Every incoming message is logged here first
-- Provides complete history of all captured thoughts

CREATE TABLE inbox_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Original message content
    raw_message TEXT NOT NULL,
    source VARCHAR(50) DEFAULT 'slack',  -- Where it came from
    
    -- AI Classification results
    category VARCHAR(50),                 -- people, projects, ideas, admin, needs_review
    confidence DECIMAL(3,2),              -- 0.00 to 1.00
    ai_title VARCHAR(255),                -- AI-generated title
    ai_response JSONB,                    -- Full AI response for debugging
    slack_thread_ts VARCHAR(50),          -- TS of original Slack message for threading
    
    -- Processing status
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    target_table VARCHAR(50),             -- Which table it was routed to
    target_id UUID                        -- ID in the target table
);

-- ============================================
-- TABLE 2: people (Contacts & Relationships)
-- ============================================
-- Track people, relationships, and follow-up needs

CREATE TABLE people (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Core info
    name VARCHAR(255) NOT NULL,
    relationship VARCHAR(100),            -- friend, colleague, client, family, etc.
    
    -- Contact details (optional)
    email VARCHAR(255),
    phone VARCHAR(50),
    
    -- Context
    notes TEXT,                           -- General notes about this person
    last_contact DATE,                    -- When you last connected
    
    -- Follow-up
    follow_up_date DATE,                  -- When to follow up
    follow_up_reason TEXT,                -- Why to follow up
    
    -- Source tracking
    inbox_log_id UUID REFERENCES inbox_log(id)
);

-- ============================================
-- TABLE 3: projects (Work & Goals)
-- ============================================
-- Track projects, goals, and work items

CREATE TABLE projects (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Core info
    title VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'active',  -- active, paused, completed, archived
    priority VARCHAR(20) DEFAULT 'medium', -- low, medium, high, urgent
    
    -- Dates
    due_date DATE,
    completed_at TIMESTAMPTZ,
    
    -- Organization
    category VARCHAR(100),                -- work, personal, side-project, etc.
    tags TEXT[],                          -- Array of tags
    
    -- Notes
    notes TEXT,                           -- Additional context
    next_action TEXT,                     -- What's the next step?
    
    -- Source tracking
    inbox_log_id UUID REFERENCES inbox_log(id)
);

-- ============================================
-- TABLE 4: ideas (Thoughts & Inspiration)
-- ============================================
-- Capture ideas, insights, and random thoughts

CREATE TABLE ideas (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Core info
    title VARCHAR(255) NOT NULL,
    content TEXT,                         -- The full idea/thought
    
    -- Classification
    category VARCHAR(100),                -- business, creative, learning, etc.
    tags TEXT[],                          -- Array of tags
    
    -- Status
    status VARCHAR(50) DEFAULT 'captured', -- captured, exploring, actionable, archived
    
    -- Links
    related_project UUID REFERENCES projects(id),
    
    -- Source tracking
    inbox_log_id UUID REFERENCES inbox_log(id)
);

-- ============================================
-- TABLE 5: admin (Tasks & To-Dos)
-- ============================================
-- Track administrative tasks and to-dos

CREATE TABLE admin (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Core info
    title VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending', -- pending, in_progress, completed, cancelled
    priority VARCHAR(20) DEFAULT 'medium', -- low, medium, high, urgent
    
    -- Dates
    due_date DATE,
    completed_at TIMESTAMPTZ,
    
    -- Organization
    category VARCHAR(100),                -- errands, bills, appointments, etc.
    
    -- Source tracking
    inbox_log_id UUID REFERENCES inbox_log(id)
);

-- ============================================
-- INDEXES for performance
-- ============================================

CREATE INDEX idx_inbox_log_created ON inbox_log(created_at DESC);
CREATE INDEX idx_inbox_log_category ON inbox_log(category);
CREATE INDEX idx_inbox_log_processed ON inbox_log(processed);

CREATE INDEX idx_people_follow_up ON people(follow_up_date);
CREATE INDEX idx_people_name ON people(name);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_due_date ON projects(due_date);

CREATE INDEX idx_ideas_status ON ideas(status);

CREATE INDEX idx_admin_status ON admin(status);
CREATE INDEX idx_admin_due_date ON admin(due_date);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================
-- Enable RLS for all tables (configure policies in Supabase dashboard)

ALTER TABLE inbox_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE people ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE ideas ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin ENABLE ROW LEVEL SECURITY;

-- ============================================
-- TABLE 6: settings (User Configuration)
-- ============================================
-- Store user preferences like timezone, digest times

CREATE TABLE settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    key VARCHAR(50) UNIQUE NOT NULL,
    value VARCHAR(255) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default settings
INSERT INTO settings (key, value) VALUES
    ('timezone', 'America/Denver'),
    ('morning_digest_hour', '7'),
    ('evening_recap_hour', '21');

-- ============================================
-- TABLE 7: reminders (Recurring Reminders)
-- ============================================
-- Track recurring reminders with flexible scheduling

CREATE TABLE reminders (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    target_table VARCHAR(50),          -- admin, projects, people, or NULL for standalone
    target_id UUID,                    -- nullable for standalone reminders
    title VARCHAR(255) NOT NULL,
    recurrence VARCHAR(20) NOT NULL,   -- daily, weekly, monthly
    next_reminder_at DATE NOT NULL,
    last_sent_at TIMESTAMPTZ,
    recurrence_day INTEGER,            -- 0-6 for weekly, 1-31 for monthly
    active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_reminders_next ON reminders(next_reminder_at) WHERE active = TRUE;

ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;

-- ============================================
-- SUCCESS MESSAGE
-- ============================================
-- If you see this, all tables were created successfully!
SELECT 'Second Brain schema created successfully!' as message;
