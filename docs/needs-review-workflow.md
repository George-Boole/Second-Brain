# Needs Review Workflow

This document explains how the Second Brain handles ambiguous or low-confidence classifications.

## Why "Needs Review" Exists

Per Nate Jones' methodology, the **Bouncer** (confidence filter) prevents low-quality outputs from polluting your memory storage. When the AI isn't confident about a classification, instead of guessing wrong and creating distrust, it asks for help.

> "The fastest way to kill a system is to fill it with garbage. The bouncer keeps things clean enough that you maintain trust." - Nate Jones

---

## When Items Go to Needs Review

An item is routed to `needs_review` when:

1. **AI explicitly classifies it as `needs_review`** - The message is too ambiguous
2. **Confidence score is below 0.6** - Even if a category was chosen, it's uncertain

### Confidence Score Guidelines

| Score | Meaning | Action |
|-------|---------|--------|
| 0.9-1.0 | Very clear, obvious classification | Route to category |
| 0.7-0.89 | Fairly confident, good match | Route to category |
| 0.6-0.69 | Somewhat uncertain | Route to category (borderline) |
| **Below 0.6** | **Uncertain, needs human review** | **Route to needs_review** |

---

## Make.com Router Configuration

### Path E Filter Condition

In your Make.com Router, add Path E with this condition:

```
category Equal to "needs_review"
OR
confidence Less than 0.6
```

### Path E Modules

1. **Supabase: Update Row** (`inbox_log`)
   - Filter: `id` = `{{inbox_log_insert_id}}`
   - Updates:
     - `processed` = `false`
     - `target_table` = `needs_review`

2. **Slack: Send Channel Message** (threaded reply)
   - Channel: `#sb-inbox`
   - Thread TS: `{{original_message_ts}}`
   - Message:
   ```
   🤔 I'm not sure how to classify this (confidence: {{confidence}})

   Could you repost with a prefix?
   - "person: ..." for people
   - "project: ..." for projects
   - "idea: ..." for ideas
   - "admin: ..." for tasks/errands

   Or reply "fix: [category]" to classify this one.
   Example: "fix: people" or "fix: admin"
   ```

---

## Reclassification Methods

### Method 1: Reply "fix: [category]" (Recommended)

Reply directly in the Slack thread:
```
fix: people
```
or
```
fix: this should be a project
```

A separate Make.com scenario ("Fix Handler") watches for these replies and:
1. Parses the new category
2. Re-processes with forced classification
3. Inserts into correct table
4. Updates inbox_log
5. Confirms in Slack

### Method 2: Repost with Prefix

Send a new message with a category prefix:
```
person: Sarah mentioned she's looking for a new marketing role
```
```
project: Need to finish the Q1 report by Friday
```

The classification prompt recognizes these prefixes and routes accordingly.

### Method 3: Manual via Supabase Dashboard

1. Open Supabase Dashboard
2. Go to Table Editor → `inbox_log`
3. Filter: `category = 'needs_review'` AND `processed = false`
4. For each item:
   - Review the `raw_message`
   - Manually insert into the correct table (people/projects/ideas/admin)
   - Update inbox_log: set `processed = true`, `target_table`, `target_id`

---

## Daily Digest Integration

The daily digest includes a **Needs Review** section when items are pending:

```
🔍 Needs Review: 3 items awaiting classification
- "The blue one is better" (0.32 confidence)
- "Remember the thing from Tuesday" (0.45 confidence)
- "Call about that" (0.38 confidence)

Reply "fix: [category]" in the original Slack thread to classify.
```

---

## Weekly Maintenance

Per Nate Jones: **"Clear Needs Review weekly, max 5 minutes"**

### Weekly Health Check

1. Open Supabase Dashboard
2. Run this query:
   ```sql
   SELECT id, ai_title, raw_message, confidence, created_at
   FROM inbox_log
   WHERE category = 'needs_review'
     AND processed = false
   ORDER BY created_at ASC;
   ```
3. Process each item (should take <5 minutes)
4. Items older than 2 weeks can usually be discarded (if you haven't needed them, you probably don't)

### Operating Rule

> "If an item sits in Needs Review for more than 2 weeks without you caring enough to classify it, it probably wasn't important. Archive it and move on." - Nate Jones principle: Design for restart, not perfection

---

## Database Schema Notes

The `inbox_log` table already has everything needed:

| Field | Purpose for Needs Review |
|-------|-------------------------|
| `category` | Set to `'needs_review'` |
| `processed` | Set to `false` (unprocessed) |
| `confidence` | Stored for visibility |
| `raw_message` | Original text for manual review |
| `ai_title` | AI's best guess at a title |
| `target_table` | Set to `'needs_review'` initially |

**No separate table required.** The inbox_log serves as the review queue.

---

## Example Test Cases

### Test 1: Ambiguous Message
**Input:** "The blue one is better for the thing we talked about."
**Expected:** `category: "needs_review"`, `confidence: ~0.3-0.4`
**Slack Reply:** Asks for clarification

### Test 2: Low Confidence Category
**Input:** "Maybe we should think about that feature sometime"
**Expected:** `category: "ideas"` or `"projects"`, `confidence: ~0.55`
**Result:** Routed to needs_review due to confidence < 0.6

### Test 3: Clear Message
**Input:** "Call mom on Sunday for her birthday"
**Expected:** `category: "admin"`, `confidence: ~0.9`
**Result:** Routed directly to admin table

---

## Troubleshooting

### Items Not Going to Needs Review
- Check Router filter: Must be `category = "needs_review" OR confidence < 0.6`
- Verify JSON parsing is extracting `confidence` field correctly

### Fix Command Not Working
- Ensure Fix Handler scenario is active
- Check trigger: must watch for threaded replies containing "fix:"
- Verify inbox_log has the Slack thread TS stored

### Too Many Items in Needs Review
- Consider adjusting confidence threshold (0.5 instead of 0.6)
- Review classification prompt for clarity
- Add few-shot examples to the prompt for common edge cases

---

## Summary

| Component | Implementation |
|-----------|---------------|
| **Storage** | `inbox_log` with `category='needs_review'`, `processed=false` |
| **Notification** | Slack threaded reply asking for fix |
| **Reclassification** | Reply "fix: [category]" or repost with prefix |
| **Visibility** | Daily digest "Needs Review" section |
| **Maintenance** | Weekly 5-minute review, 2-week archive rule |
