# Voice Capture via Siri Shortcuts

Capture thoughts to your Second Brain using just your voice — no typing, no opening Telegram.

This shortcut calls the Telegram Bot API directly via HTTP, so it works reliably without depending on Telegram's Shortcuts integration.

## What You'll Need

- Your **Bot Token** (from your `.env` or Vercel environment variables — the `TELEGRAM_BOT_TOKEN` value)
- Your **Telegram User ID** (send `/myid` to the bot to get it)

## Setup (3 minutes)

1. Open the **Shortcuts** app on your iPhone
2. Tap **+** to create a new shortcut

### Action 1: Dictate Text
- Search for **"Dictate Text"**
- Tap to add it
- Set "Stop Listening" to **After Pause** (so it stops when you finish speaking)

### Action 2: Get Contents of URL (send to bot)
- Search for **"Get Contents of URL"**
- Tap to add it
- Set the URL to:
  ```
  https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage
  ```
  Replace `<YOUR_BOT_TOKEN>` with your actual bot token.
- Tap **Show More** and configure:
  - **Method:** POST
  - **Request Body:** JSON
  - Add two keys:
    | Key | Type | Value |
    |-----|------|-------|
    | `chat_id` | Number | Your Telegram user ID |
    | `text` | Text | Select the **Dictated Text** variable from Action 1 |

3. Tap the shortcut name at the top and rename it: **"Second Brain"**
4. Tap **Done** to save

## Usage

Say:
> "Hey Siri, Second Brain"

Then speak your thought naturally. Examples:

- "Call the dentist tomorrow"
- "Project idea: build a meal planning app"
- "Follow up with Sarah about the contract next week"
- "Admin: renew car registration by March 15th"

The bot will automatically classify and store your thought.

## Optional: Assign to Action Button

On iPhone 15 Pro / 16 Pro:
1. Go to **Settings > Action Button**
2. Select **Shortcut**
3. Choose your **Second Brain** shortcut
4. Press and hold the Action Button to capture a thought anytime

## Tips for Better Classification

### Use category prefixes when needed
- **"admin:"** — tasks (dentist, bills, errands)
- **"project:"** — project-related items
- **"person:"** — people follow-ups
- **"idea:"** — ideas to explore later

### Speak completion updates
- "I finished the quarterly report"
- "Done with the dentist appointment"

The bot will detect these and mark the matching task complete.

### Include dates naturally
- "...by Friday"
- "...next Tuesday"
- "...in two weeks"

## Troubleshooting

### Shortcut fails with an error?
- Double-check the bot token in the URL (no extra spaces)
- Make sure `chat_id` is set to **Number** type, not Text
- Verify the bot is running by sending a manual message in Telegram

### Dictation stops too quickly?
- Set "Stop Listening" to **After Pause** instead of **After Short Pause**
- Or switch to **"Ask for Input"** action with **Type: Text** for a typed fallback

### Classification seems wrong?
- Use category prefixes for better accuracy
- Tap the "Fix" buttons in the bot to reclassify

## Quick Reference

| Voice Command | Result |
|---------------|--------|
| "Hey Siri, Second Brain" | Opens dictation |
| "admin: dentist Friday" | Creates admin task |
| "Call Sarah next week" | Creates people follow-up |
| "I finished the report" | Marks task complete |
| "project: launch marketing campaign" | Creates project item |
