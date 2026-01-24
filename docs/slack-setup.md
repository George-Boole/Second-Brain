# Slack Setup Guide

## Overview

We'll create a dedicated Slack workspace for your Second Brain. Voice messages sent here will be automatically captured, transcribed, and processed.

---

## Step 1: Create Slack Workspace

1. Go to **[slack.com/create](https://slack.com/create)**
2. Enter your email and click **Continue**
3. Enter the confirmation code from your email
4. Name your workspace: `Second Brain` (or similar)
5. Skip inviting teammates (click "Skip this step")
6. Skip the channel creation prompt for now

---

## Step 2: Create the Inbox Channel

1. In your new workspace, click **+ Add channels** in the sidebar
2. Click **Create a new channel**
3. Name it: `sb-inbox`
4. Description: `Voice messages for Second Brain capture`
5. Keep it as **Public** (easier for Make.com integration)
6. Click **Create**

---

## Step 3: Test Voice Messages

### On Mobile (Recommended):
1. Open Slack app on your phone
2. Go to `#sb-inbox` channel
3. Tap the **+** button → **Record audio clip**
4. Record a test message: "This is a test for my second brain"
5. Send it

### On Desktop:
1. In the `#sb-inbox` channel
2. Click the **+** button in the message field
3. Select **Record audio clip** (or use the microphone icon)
4. Record and send

---

## Step 4: Verify Transcription

After sending a voice message:
1. You should see the audio clip in the channel
2. Slack automatically transcribes it (may take a few seconds)
3. Click on the audio message to see the transcription
4. ✅ If you see text transcription, you're ready!

> **Note:** Slack's transcription is included in all plans, including free.

---

## What You'll Need for Make.com

When we set up Make.com, you'll need:

1. **Slack Bot Token** - We'll create a Slack App
2. **Channel ID** - The ID of `#sb-inbox`

We'll cover this in Step 8-10 when building the Make.com flow.

---

## Troubleshooting

### No transcription showing?
- Wait 10-30 seconds, transcription can be slow
- Try a longer message (very short clips sometimes fail)
- Check Slack is updated to latest version

### Can't find voice message option?
- Update your Slack app
- Voice messages are called "Audio clips" in newer versions

---

## Checklist

- [ ] Created Slack workspace
- [ ] Created `#sb-inbox` channel
- [ ] Sent test voice message
- [ ] Confirmed transcription works
