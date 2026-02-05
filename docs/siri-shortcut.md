# Voice Capture via Siri Shortcuts

Capture thoughts to your Second Brain using just your voice - no typing required!

## Setup (2 minutes)

1. Open the **Shortcuts** app on your iPhone
2. Tap **+** to create a new shortcut
3. Add these two actions in order:

### Action 1: Dictate Text
- Tap "Add Action" or search at the top
- Search for **"Dictate Text"**
- Tap to add it
- (Optional) Set language and "Stop Listening" behavior

### Action 2: Send Message via Telegram
- Search for **"Telegram"**
- Select **"Send Message"**
- For **Recipient**: Search for and select your Second Brain bot
- For **Message**: Tap the field, then select the **"Dictated Text"** variable from above

4. Tap the shortcut name at the top to rename it: **"Second Brain"**
5. Tap **Done** to save

## Usage

Say:
> "Hey Siri, Second Brain"

Then speak your thought naturally. Examples:

- "Call the dentist tomorrow"
- "Project idea: build a meal planning app"
- "Follow up with Sarah about the contract next week"
- "Admin: renew car registration by March 15th"

The bot will automatically classify and store your thought.

## Tips for Better Classification

### Use category prefixes when needed
- **"admin:"** - for tasks (dentist, bills, errands)
- **"project:"** - for project-related items
- **"person:"** - for people follow-ups
- **"idea:"** - for ideas to explore later

### Speak completion updates
- "I finished the quarterly report"
- "Done with the dentist appointment"
- "Completed the website redesign"

The bot will detect these and mark the matching task complete.

### Include dates naturally
- "...by Friday"
- "...next Tuesday"
- "...in two weeks"

## Troubleshooting

### Shortcut doesn't work?
1. Make sure Telegram is installed and you're logged in
2. Open Telegram and send any message to your bot manually first (this authorizes the connection)
3. Try the shortcut again

### Bot doesn't respond?
- Check that the bot is running (send a test message manually)
- Verify you're sending to the correct bot

### Classification seems wrong?
- Use category prefixes for better accuracy
- You can always tap "Fix" buttons in the bot to reclassify

## Alternative: Siri with Reminders Integration

If you prefer using Reminders app:

1. "Hey Siri, remind me to [task]"
2. Set up iOS Automation to forward new Reminders to Telegram

This requires additional IFTTT or automation setup.

## Quick Reference

| Voice Command | Result |
|---------------|--------|
| "Hey Siri, Second Brain" | Opens dictation |
| "admin: dentist Friday" | Creates admin task |
| "Call Sarah next week" | Creates people follow-up |
| "I finished the report" | Marks task complete |
| "project: launch marketing campaign" | Creates project item |
