# Voice Capture

Voice capture via Siri Shortcuts is a planned future feature. The current approach (direct API endpoint) needs further debugging to work reliably with iOS Shortcuts.

## Current Status: Not Yet Working

### What exists:
- `/api/capture` endpoint deployed on Vercel (accepts POST with `user_id` and `text`)
- Endpoint runs full classification pipeline and sends confirmation via Telegram

### What needs investigation:
- iOS Shortcuts "Get Contents of URL" action not successfully reaching the endpoint
- May need debugging with Vercel logs to identify the failure point

## Workarounds

For now, use one of these approaches:
- **Type in Telegram** — send messages directly to the bot
- **iOS dictation in Telegram** — tap the text field, then tap the microphone icon on the iOS keyboard to dictate
- **Category prefixes** — start with `admin:`, `project:`, `person:`, or `idea:` for accurate classification
