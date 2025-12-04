# Clash Royale Spy Bot

## Clash royale monitoring system, that works through telegram bot.
# Bot is able to:

Search players through official API

Monitor players 24/7 and recieve live notifications when user plays a match, changes deck and more.

Automatically calculates winrate based on previous matches, by gamemode, by opponent (2+ matches) and overall.

Automatically detect when user plays against the same opponent.

Simultaneously monitor unlimited amount of players (Works with default rate limits)

Store data locally, so even if the bot is turned off data is preserved for future.

---

## Setup

### Step 1: Install Dependencies

```
pip install -r requirements.txt
```

### Step 2: Create API Key Files

Create these two files in the project folder:

**File: `telegramapi.env`**
```
your_telegram_bot_token_here
```
Get your token from [@BotFather](https://t.me/BotFather) on Telegram.

**File: `royaleapi.env`**
```
your_clash_royale_api_key_here
```
Get your API key from https://developer.clashroyale.com

### Step 3: Set Up Telegram Group

1. Create a new Telegram group
2. Go to group Settings
3. Enable **Topics** (this is required!)
4. Add your bot to the group
5. Make the bot an **Admin**
6. Get your group ID and update `ALLOWED_GROUP_ID` in `bot.py`

**How to get group ID:**
- Add [@userinfobot](https://t.me/userinfobot) to your group
- It will show the group ID (starts with `-100`)

### Step 4: Run

```
python bot.py
```

---

## Commands

- `/search <tag>` - Search for player info
- `/monitor <tag>` - Start monitoring a player
- `/unmonitor <tag>` - Stop monitoring
- `/listmonitors` - List monitored players
- `/stats <tag>` - View battle statistics
- `/rivals <tag>` - Show repeat opponents
- `/rivals <tag> <opponent>` - Head-to-head stats

Tags work with or without `#` (e.g., `#ABC123` or `ABC123`)
