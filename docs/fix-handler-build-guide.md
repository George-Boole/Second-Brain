# Fix Handler Scenario - Complete Build Guide

> [!IMPORTANT]
> **Zero-Error Policy: Authoritative Documentation**
> **All agents working on this must refer to authoritative documentation (e.g., official API docs, library references) while making a plan and creating instructions.**
> *   **Do not guess** or rely on training data for API schemas, field names, or specific tool behaviors.
> *   **Verify** specific syntax in the official documentation for the tool (Make.com, Slack API, OpenAI API, etc.).
> *   **Do not assume** standard behavior matches the tool's specific implementation (e.g., Make.com's Regex engine is unique).
> *   If unsure, perform a controlled isolation test (Run Module Only) before integrating.

## ⚠️ Prerequisite: Update MAIN Scenario First
Before creating this new scenario, you must update your **existing** "Slack to Second Brain" scenario to IGNORE fix messages.

1. Open your **Main Scenario** (Slack to Second Brain)
2. Click the **wrench icon** (filter) between Slack and the next module
3. Add a condition:
   - **Text** (from Slack) -> **Text operators: Does not match pattern** -> `(?i)^fix:`
4. Click **OK** and **Save**
5. This prevents the main bot from treating "fix: people" as a new note.

---

## Step 1: Clone & Prepare Scenario
Instead of starting from scratch, we will clone your existing scenario to keep the Slack connection.

1. Go to your **Scenarios** list in Make.com
2. Find your **Main Scenario** (Slack to Second Brain)
3. Right-click (or click the three dots) -> **Clone**
4. Name it: `Second Brain - Fix Handler`
5. Turn **OFF** the "scheduling" (Run: Immediately is fine, but don't activate yet)
6. Open the new `Second Brain - Fix Handler` scenario

## Step 2: Modify the Flow (Don't Delete!)
We will keep the Router and destination paths to save time. We just need to change the "Input" side.

1.  **Unlink** the Slack module from the OpenAI module (right-click the dotted line -> Unlink, or drag them apart).
2.  **Delete** the single **Supabase** module that sits **BETWEEN** the JSON module and the Router. (We don't need to create a new log, we are fixing an existing one).
3.  **Move** the Slack module to the far left.

## Step 3: Insert New Modules
1.  Add a **Text Parser -> Match Pattern** module after Slack.
2.  Add a **Supabase -> Select Rows** module after Text Parser.
3.  Connect them in this order:
    **Slack** → **Text Parser** → **Supabase (Select)** → **OpenAI** → **JSON** → **Router**...


---

## Module 2: Text Parser - Match Pattern
1. Click the **+** button next to the Slack module
2. Search: `text parser`
3. Select: **Text parser → Match pattern**
4. Configure ALL fields:

| Field | Value |
|-------|-------|
| **Pattern** | `fix:\s*(\w+)` (Do NOT use `(?i)`) |
| **Text** | Click field → Select **1. Text** from Slack module |
| **Global match** | No |
| **Case sensitive** | No |
| **Multiline** | No |
| **Continue execution even if module finds no match** | No |

5. Click **Save**

---

## Module 3: Supabase - Select Rows
1. Click the **+** button next to the Text Parser module
2. Search: `supabase`
3. Select: **Supabase → Select Rows**
4. Configure ALL fields:

| Field | Value |
|-------|-------|
| **Connection** | My Supabase connection |
| **Table** | `inbox_log` |
| **Filter** | Click "Add" |
| **Filter - Column** | `slack_thread_ts` |
| **Filter - Operator** | `eq` (equals) |
| **Filter - Value** | Click field → Expand **1. Slack** → Select **Thread ID** (or **Thread TS** if that's what it's called) |
| **Order By** | Leave empty |
| **Limit** | `1` |

5. Click **Save**

---

## Slack & Text
> [!NOTE]
> **Re-categorization Logic**: Currently, this scenario **adds** the item to the new category and updates the `inbox_log`. It does *not* yet automatically delete the item from the *old* category if it was previously misclassified. (e.g., if moved from Ideas -> Projects, it will exist in both until manually deleted). This cleanup logic is planned for a future update.

## 1. Scenario Configuration Tips
### 1. Slack - Watch Public Channel Messages
*   **Connection**: Select your Slack connection.
*   **Channel**: `sb-inbox`
*   **Limit**: `1`
*   **IMPORTANT**: Using the standard "Watch Public Channel" module in Make.com often misses threaded replies.
    *   **Workaround**: When replying in Slack with `fix: [category]`, you MUST check the box **"Also send to #sb-inbox"**. This broadcasts the reply so the watcher sees it.

---

## Module 4: OpenAI - Create a Completion
1. Click the **+** button next to Supabase module
2. Search: `openai`
3. Select: **OpenAI (ChatGPT, DALL-E, Whisper) → Create a Completion**
4. Configure ALL fields:

| Field | Value |
|-------|-------|
| **Connection** | Your OpenAI connection |
| **Method** | Create a Chat Completion |
| **Model** | `gpt-4o` or `gpt-4o-mini` |
| **Messages** | Click **Add item** |
| **Messages → Role** | `system` |
| **Messages → Message Content** | Paste contents of `prompts/fix-handler-prompt.txt` |
| **Messages** | Click **Add item** again |
| **Messages → Role** | `user` |
| **Messages → Message Content** | Type: `Message: ` then map **3. raw_message** from Supabase, then type ` Category: ` then map **2. $1** from Text Parser |
| **Max Tokens** | `500` |
| **Temperature** | `0.3` |

5. Click **Save**

---

## Module 5: JSON - Parse JSON
1. Click **+** next to OpenAI module
2. Search: `json`
3. Select: **JSON → Parse JSON**
4. Configure:

| Field | Value |
|-------|-------|
| **JSON string** | Map **4. Result** from OpenAI module |

5. Click **Save**

---

## Module 6: Router
1. Click **+** next to JSON module
2. Search: `router`
3. Select: **Flow Control → Router**
4. No configuration needed, just add it

---

## Module 7-10: Four Supabase Upsert Modules (one per path)

For EACH path from the router, add a **Supabase → Upsert a Record** module:

### Path 1: People
| Field | Value |
|-------|-------|
| **Table** | `people` |
| **name** | Map **5. title** from JSON |
| **context** | Map **5. summary** from JSON |
| **follow_up** | Map **5. follow_up** from JSON |

**Filter on the line BEFORE this module:**
- Click the dotted line between Router and this module
- Label: `Is People`
- Condition: **5. category** (from JSON) → **Text operators: Equal to** → `people`

### Path 2: Projects
| Field | Value |
|-------|-------|
| **Table** | `projects` |
| **name** | Map **5. title** from JSON |
| **description** | Map **5. summary** from JSON |
| **next_action** | Map **5. next_action** from JSON |
| **deadline** | Map **5. due_date** from JSON |

**Filter:** category equals `projects`

### Path 3: Ideas
| Field | Value |
|-------|-------|
| **Table** | `ideas` |
| **title** | Map **5. title** from JSON |
| **content** | Map **5. summary** from JSON |

**Filter:** category equals `ideas`

### Path 4: Admin
| Field | Value |
|-------|-------|
| **Table** | `admin` |
| **task** | Map **5. title** from JSON |
| **notes** | Map **5. summary** from JSON |
| **due_date** | Map **5. due_date** from JSON |

**Filter:** category equals `admin`

---

## Module 11: Supabase - Upsert inbox_log (after each path)
After EACH of the 4 category modules, add:

1. **Supabase → Upsert a Record**
2. Configure:

| Field | Value |
|-------|-------|
| **Table** | `inbox_log` |
| **id** | Map **3. id** from the earlier Supabase Select module |
| **processed** | `Yes` |
| **processed_at** | `{{now}}` |
| **target_table** | Map **5. category** from JSON |

---

## Step 5: Slack Confirmation (Add to ALL 4 Output Paths)
> [!NOTE]
> **Why 4 times?** We need to ensure the confirmation happens *after* the database update is successful.

1.  **Create the Module Once**:
    *   Right-click empty space -> **Add a module**.
    *   Select **Slack → Send a Message**.
    *   **Connection**: Your Slack connection.
    *   **Channel type**: `Public channel`.
    *   **Public channel**: `sb-inbox`.
    *   **Text**: `✅ Got it! Moved to *{{5.category}}*: "{{5.title}}"`
    *   **Thread ID**: Map **1. Message ID (timestamp)** from the original Slack module.
        *   *Tip*: If this doesn't reply to the thread you expect, check if your trigger message was already a reply. If so, map **1. Thread TS** (if available) or create a variable `{{ifempty(1.Thread TS; 1.TS)}}`.

2.  **Duplicate**:
    *   Clone this module 3 times.
    *   Connect one to the END of each path (after the `inbox_log` update).

---

## Step 6: Cleanup Logic (Dynamic Delete)
We need to remove the entry from its *old* table to prevent duplicates.
We will use the **Supabase → Make an API Call** module because it allows us to dynamically select the table name using the data from Module 3.

1.  **Create the Cleanup Module**:
    *   Right-click empty space -> **Add a module**.
    *   Search **Supabase**.
    *   Select **Supabase → Make an API Call**.
    *   **Connection**: Your Supabase connection.
    *   **URL**: `/{{3.target_table}}?id=eq.{{3.target_id}}`
        *   *Note*: This uses the `target_table` (e.g., 'ideas') and `target_id` (UUID) retrieved from the `inbox_log` in Module 3.
    *   **Method**: `DELETE`.

2.  **Duplicate and Connect**:
    *   Clone this module 3 times.
    *   Connect one to the END of each path (after the Slack Confirmation).

3.  **Add Safety Filter**:
    *   We should only try to delete if we actually found a previous record.
    *   Click the dotted line between **Slack Confirmation** and **Cleanup Module**.
    *   **Label**: `Cleanup?`
    *   **Condition**:
        *   **3. target_table** -> **Basic operators: Exists** (not empty).
        *   AND
        *   **3. target_id** -> **Basic operators: Exists**.
    *   Repeat this filter for all 4 paths.

---

## 4. Testing & Verification

1.  **Preparation**:
    *   Ensure the scenario is **ON** (or click "Run Once").

2.  **Trigger Test**:
    *   Go to Slack `sb-inbox`.
    *   Find a message that needs fixing.
    *   Reply: `fix: projects`.
    *   **CRITICAL**: Check the **"Also send to #sb-inbox"** box before hitting Enter.

3.  **Verify**:
    *   Check `inbox_log` in Supabase: The category should change to `projects`.
    *   Check Slack: You should see a confirmation reply in the thread.
    *   Check Make.com history: All bubbles should be green.
    *   **Clean Up Check**: Verify the item was DELETED from the old table (e.g., Ideas) and exists in the new table (Projects).

### Troubleshooting
*   **Text Parser not showing variables?** The module hasn't matched anything yet. Force a successful run using the "Also send to channel" trick to populate the variables.
*   **OpenAI outputs "13.1"?** You mapped the *name* of the variable instead of the *value*. Delete the text and drag the actual bubble from the picker.
*   **Scenario stops at Text Parser?** The trigger message didn't match the regex. Ensure you triggered it with a valid `fix: category` message.
*   **Cleanup failed?** Check Module 3's output. Did it find a `target_table` and `target_id`? If not, the old record wasn't properly logged or processed.
