import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

from clash_api import ClashRoyaleAPI
from formatters import (
    format_player_info, format_battle, format_battle_short,
    format_rivals_list, format_opponent_detail, format_repeat_opponent_alert
)
from battle_logger import (
    add_battle, get_player_stats, ensure_monitoring_dir,
    load_player_data, save_player_data, get_repeat_opponents,
    get_opponent_history
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
ALLOWED_GROUP_ID = -1003474155849
MONITOR_FILE = "monitored_players.json"
CHECK_INTERVAL = 60  # Check for new battles every 60 seconds (1 minute)
PLAYER_CHECK_DELAY = 2  # Delay between checking each player (seconds) to avoid rate limiting

# Global state
monitored_players: dict = {}  # {player_tag: {"topic_id": int, "last_battle_time": str, "name": str, "pinned_message_id": int}}
clash_api: Optional[ClashRoyaleAPI] = None


def load_env_file(filepath: str) -> str:
    """Load a value from a simple env file"""
    with open(filepath, "r") as f:
        return f.read().strip()


def load_monitored_players():
    """Load monitored players from file"""
    global monitored_players
    if os.path.exists(MONITOR_FILE):
        with open(MONITOR_FILE, "r") as f:
            monitored_players = json.load(f)
    logger.info(f"Loaded {len(monitored_players)} monitored players")


def save_monitored_players():
    """Save monitored players to file"""
    with open(MONITOR_FILE, "w") as f:
        json.dump(monitored_players, f, indent=2)


def check_group_access(update: Update) -> bool:
    """Check if command is from allowed group"""
    chat_id = update.effective_chat.id
    if chat_id != ALLOWED_GROUP_ID:
        logger.warning(f"Unauthorized access attempt from chat {chat_id}")
        return False
    return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    if not check_group_access(update):
        await update.message.reply_text("This bot only works in the authorized group.")
        return

    await update.message.reply_text(
        "Clash Royale Monitor Bot\n\n"
        "Available commands:\n"
        "- /search <playertag> - Search for player info\n"
        "- /monitor <playertag> - Start monitoring a player (creates a topic)\n"
        "- /unmonitor <playertag> - Stop monitoring a player (closes topic)\n"
        "- /listmonitors - List all monitored players\n"
        "- /stats <playertag> - View monitored battle statistics\n"
        "- /rivals <playertag> - Show repeat opponents (rivalries)\n"
        "- /rivals <playertag> <opponent> - Head-to-head stats vs opponent\n\n"
        "Player tags can be with or without #\n\n"
        "Make sure this group has Topics enabled!"
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command"""
    if not check_group_access(update):
        await update.message.reply_text("This bot only works in the authorized group.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /search <playertag>")
        return

    player_tag = context.args[0].upper()
    if not player_tag.startswith("#"):
        player_tag = "#" + player_tag

    await update.message.reply_text(f"🔍 Searching for player {player_tag}...")

    try:
        # Fetch player data
        player = await clash_api.get_player(player_tag)
        chests = await clash_api.get_player_chests(player_tag)

        # Fetch clan data if player is in a clan
        clan = None
        if player.get("clan"):
            try:
                clan = await clash_api.get_clan(player["clan"]["tag"])
            except Exception as e:
                logger.warning(f"Could not fetch clan data: {e}")

        # Get monitored stats if available
        monitored_stats = get_player_stats(player_tag)

        # Format and send response
        msg = format_player_info(player, clan, chests, monitored_stats)

        # Split message if too long (Telegram limit is 4096 chars)
        if len(msg) > 4000:
            parts = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(msg)

    except ValueError as e:
        await update.message.reply_text(f"❌ Player not found: {player_tag}")
    except PermissionError as e:
        await update.message.reply_text("❌ API key error. Please check configuration.")
    except Exception as e:
        logger.error(f"Error searching player: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show monitored battle statistics"""
    if not check_group_access(update):
        await update.message.reply_text("This bot only works in the authorized group.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /stats <playertag>")
        return

    player_tag = context.args[0].upper()
    if not player_tag.startswith("#"):
        player_tag = "#" + player_tag

    stats = get_player_stats(player_tag)

    if not stats or stats.get("total", {}).get("total", 0) == 0:
        await update.message.reply_text(f"📊 No battle statistics recorded for {player_tag}")
        return

    total = stats["total"]
    msg = f"📊 Battle Statistics for {player_tag}\n"
    msg += "=" * 40 + "\n\n"
    msg += f"Total: {total['wins']}W / {total['losses']}L / {total['draws']}D\n"
    msg += f"Games Played: {total['total']}\n"
    msg += f"Win Rate: {total['win_rate']}%\n\n"
    msg += "BY GAME MODE:\n"
    msg += "-" * 20 + "\n"

    sorted_modes = sorted(
        stats["by_mode"].items(),
        key=lambda x: x[1]["total"],
        reverse=True
    )

    for mode, mode_stats in sorted_modes:
        msg += f"\n{mode}:\n"
        msg += f"  Record: {mode_stats['wins']}W / {mode_stats['losses']}L / {mode_stats['draws']}D\n"
        msg += f"  Games: {mode_stats['total']} | Win Rate: {mode_stats['win_rate']}%\n"

    await update.message.reply_text(msg)


async def rivals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rivals command - show repeat opponents and head-to-head stats"""
    if not check_group_access(update):
        await update.message.reply_text("This bot only works in the authorized group.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n"
            "/rivals <playertag> - Show all repeat opponents\n"
            "/rivals <playertag> <opponent_tag> - Show detailed stats vs specific opponent"
        )
        return

    player_tag = context.args[0].upper()
    if not player_tag.startswith("#"):
        player_tag = "#" + player_tag

    # Check if asking for specific opponent
    if len(context.args) >= 2:
        opponent_tag = context.args[1].upper()
        if not opponent_tag.startswith("#"):
            opponent_tag = "#" + opponent_tag

        # Get detailed history against specific opponent
        opponent = get_opponent_history(player_tag, opponent_tag)
        if not opponent:
            await update.message.reply_text(
                f"No match history found between {player_tag} and {opponent_tag}"
            )
            return

        msg = format_opponent_detail(opponent)
        await update.message.reply_text(msg)
        return

    # Get player name for display
    player_data = monitored_players.get(player_tag, {})
    player_name = player_data.get("name", player_tag)

    # Get repeat opponents
    rivals = get_repeat_opponents(player_tag, min_matches=2)

    if not rivals:
        await update.message.reply_text(
            f"No repeat opponents found for {player_name} ({player_tag}).\n"
            "Keep playing to track your rivalries!"
        )
        return

    msg = format_rivals_list(rivals, player_name)

    # Split message if too long
    if len(msg) > 4000:
        parts = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(msg)


async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /monitor command - creates a forum topic and monitors player"""
    if not check_group_access(update):
        await update.message.reply_text("This bot only works in the authorized group.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /monitor <playertag>")
        return

    player_tag = context.args[0].upper()
    if not player_tag.startswith("#"):
        player_tag = "#" + player_tag

    # Check if already monitoring
    if player_tag in monitored_players:
        topic_id = monitored_players[player_tag].get("topic_id")
        await update.message.reply_text(
            f"⚠️ Already monitoring {player_tag}\n"
            f"Topic ID: {topic_id}"
        )
        return

    await update.message.reply_text(f"🔄 Setting up monitoring for {player_tag}...")

    # Ensure monitoring directory exists
    ensure_monitoring_dir()

    try:
        # Fetch player info
        player = await clash_api.get_player(player_tag)
        chests = await clash_api.get_player_chests(player_tag)

        player_name = player.get("name", "Unknown")
        clean_tag = player_tag.replace("#", "")

        bot: Bot = context.bot
        topic_name = f"{player_name} ({clean_tag})"

        try:
            # Create a forum topic for this player
            forum_topic = await bot.create_forum_topic(
                chat_id=ALLOWED_GROUP_ID,
                name=topic_name,
                icon_custom_emoji_id=None
            )

            topic_id = forum_topic.message_thread_id
            logger.info(f"Created forum topic '{topic_name}' with ID {topic_id}")

            # Get clan info
            clan = None
            if player.get("clan"):
                try:
                    clan = await clash_api.get_clan(player["clan"]["tag"])
                except:
                    pass

            # Get existing stats if any
            monitored_stats = get_player_stats(player_tag)

            msg = f"🔔 MONITORING STARTED\n\n{format_player_info(player, clan, chests, monitored_stats)}"

            # Send and pin the message in the topic
            sent_msg = await bot.send_message(
                chat_id=ALLOWED_GROUP_ID,
                message_thread_id=topic_id,
                text=msg[:4000]
            )

            pinned_message_id = sent_msg.message_id

            # Pin the message in the topic
            try:
                await bot.pin_chat_message(
                    chat_id=ALLOWED_GROUP_ID,
                    message_id=pinned_message_id,
                    disable_notification=True
                )
            except Exception as e:
                logger.warning(f"Could not pin message: {e}")

            # Get last battle time with timeout handling
            last_battle_time = ""
            try:
                battles = await asyncio.wait_for(
                    clash_api.get_player_battles(player_tag),
                    timeout=10.0
                )
                if battles:
                    last_battle_time = battles[0].get("battleTime", "")
                    # Log existing battles to file
                    for battle in reversed(battles):
                        add_battle(player_tag, battle)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout getting battles for {player_tag}, starting fresh")

            # Get current arena
            current_arena = player.get("arena", {}).get("name", "")

            # Save to monitored players
            monitored_players[player_tag] = {
                "topic_id": topic_id,
                "last_battle_time": last_battle_time,
                "name": player_name,
                "pinned_message_id": pinned_message_id,
                "last_arena": current_arena
            }
            save_monitored_players()

            await update.message.reply_text(
                f"✅ Now monitoring {player_name} ({player_tag})\n"
                f"📌 Topic created: {topic_name}\n"
                f"Battle updates will be posted to the topic.\n"
                f"Stats will be saved to monitoring/{clean_tag}.json"
            )

        except Exception as e:
            logger.error(f"Error creating topic/monitoring: {e}")
            await update.message.reply_text(f"❌ Error setting up monitoring: {str(e)}\n\n⚠️ Make sure this group has Topics enabled!")

    except ValueError:
        await update.message.reply_text(f"❌ Player not found: {player_tag}")
    except Exception as e:
        logger.error(f"Error in monitor command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def unmonitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unmonitor command"""
    if not check_group_access(update):
        await update.message.reply_text("This bot only works in the authorized group.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /unmonitor <playertag>")
        return

    player_tag = context.args[0].upper()
    if not player_tag.startswith("#"):
        player_tag = "#" + player_tag

    if player_tag not in monitored_players:
        await update.message.reply_text(f"⚠️ Player {player_tag} is not being monitored.")
        return

    player_data = monitored_players.pop(player_tag)
    save_monitored_players()

    # Try to close the topic
    bot: Bot = context.bot
    topic_id = player_data.get("topic_id")

    if topic_id:
        try:
            await bot.close_forum_topic(
                chat_id=ALLOWED_GROUP_ID,
                message_thread_id=topic_id
            )
            await update.message.reply_text(
                f"✅ Stopped monitoring {player_data['name']} ({player_tag})\n"
                f"📌 Topic has been closed.\n"
                f"📊 Battle logs are preserved in the monitoring folder."
            )
        except Exception as e:
            logger.warning(f"Could not close topic: {e}")
            await update.message.reply_text(
                f"✅ Stopped monitoring {player_data['name']} ({player_tag})\n"
                f"⚠️ Could not close topic automatically."
            )
    else:
        await update.message.reply_text(
            f"✅ Stopped monitoring {player_data['name']} ({player_tag})"
        )


async def list_monitors_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all monitored players"""
    if not check_group_access(update):
        await update.message.reply_text("This bot only works in the authorized group.")
        return

    if not monitored_players:
        await update.message.reply_text("📋 No players are currently being monitored.")
        return

    msg = "📋 Monitored Players:\n\n"
    for tag, data in monitored_players.items():
        topic_id = data.get("topic_id", "N/A")
        stats = get_player_stats(tag)
        total_games = stats.get("total", {}).get("total", 0) if stats else 0
        win_rate = stats.get("total", {}).get("win_rate", 0) if stats else 0
        msg += f"• {data['name']} ({tag})\n"
        msg += f"  Topic #{topic_id} | {total_games} games | {win_rate}% WR\n"

    await update.message.reply_text(msg)


async def update_pinned_message(bot: Bot, player_tag: str, data: dict):
    """Update the pinned message with fresh player data (text only)"""
    try:
        topic_id = data.get("topic_id")
        pinned_message_id = data.get("pinned_message_id")

        if not topic_id or not pinned_message_id:
            return

        # Fetch fresh player data with timeout
        try:
            player = await asyncio.wait_for(
                clash_api.get_player(player_tag),
                timeout=15
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching player data for {player_tag}, skipping update")
            return

        try:
            chests = await asyncio.wait_for(
                clash_api.get_player_chests(player_tag),
                timeout=15
            )
        except asyncio.TimeoutError:
            chests = {"items": []}

        clan = None
        if player.get("clan"):
            try:
                clan = await asyncio.wait_for(
                    clash_api.get_clan(player["clan"]["tag"]),
                    timeout=10
                )
            except:
                pass

        # Get monitored stats
        monitored_stats = get_player_stats(player_tag)

        msg = f"🔔 MONITORING ACTIVE\n\n{format_player_info(player, clan, chests, monitored_stats)}"

        # Edit the pinned message with timeout
        try:
            await asyncio.wait_for(
                bot.edit_message_text(
                    chat_id=ALLOWED_GROUP_ID,
                    message_id=pinned_message_id,
                    text=msg[:4000]
                ),
                timeout=15
            )
            logger.debug(f"Updated pinned message for {player_tag}")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout editing pinned message for {player_tag}")

    except Exception as e:
        logger.error(f"Error updating pinned message for {player_tag}: {e}")


async def check_battles(app: Application):
    """Background task to check for new battles and update stats"""
    bot = app.bot

    while True:
        try:
            for player_tag, data in list(monitored_players.items()):
                try:
                    # Fetch battles with timeout
                    try:
                        battles = await asyncio.wait_for(
                            clash_api.get_player_battles(player_tag),
                            timeout=20
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout fetching battles for {player_tag}")
                        await asyncio.sleep(PLAYER_CHECK_DELAY)
                        continue

                    if not battles:
                        # Still update the pinned message even if no new battles
                        await update_pinned_message(bot, player_tag, data)
                        await asyncio.sleep(PLAYER_CHECK_DELAY)
                        continue

                    last_known_time = data.get("last_battle_time", "")
                    topic_id = data.get("topic_id")

                    if not topic_id:
                        logger.warning(f"No topic_id for player {player_tag}, skipping")
                        continue

                    # Find new battles
                    new_battles = []
                    for battle in battles:
                        battle_time = battle.get("battleTime", "")
                        if battle_time and battle_time > last_known_time:
                            new_battles.append(battle)
                        else:
                            break  # Battles are sorted by time desc

                    # Process new battles (oldest first)
                    had_new_battles = len(new_battles) > 0

                    for battle in reversed(new_battles):
                        # Check for repeat opponent BEFORE adding the battle
                        enemy_tag = ""
                        team = battle.get("team", [])
                        opponent = battle.get("opponent", [])
                        for t in team:
                            if t.get("tag", "").upper() == player_tag.upper():
                                enemy_tag = opponent[0].get("tag", "").upper() if opponent else ""
                                break
                        if not enemy_tag:
                            for o in opponent:
                                if o.get("tag", "").upper() == player_tag.upper():
                                    enemy_tag = team[0].get("tag", "").upper() if team else ""
                                    break

                        # Get previous history with this opponent (before recording current battle)
                        previous_opponent_stats = get_opponent_history(player_tag, enemy_tag) if enemy_tag else None

                        # Log battle to file and get updated stats
                        stats = add_battle(player_tag, battle)

                        # Format battle message
                        msg = format_battle_short(battle, player_tag)

                        # Add repeat opponent alert if this is a rematch
                        if previous_opponent_stats and previous_opponent_stats.get("total", 0) >= 1:
                            # Get updated opponent stats after recording this battle
                            updated_opponent = get_opponent_history(player_tag, enemy_tag)
                            if updated_opponent:
                                rival_msg = format_repeat_opponent_alert(updated_opponent, is_new_battle=False)
                                msg += f"\n\n🎯 {rival_msg}"

                        # Add current session stats to battle notification
                        if stats and stats.get("total", {}).get("total", 0) > 0:
                            total = stats["total"]
                            msg += f"\n\n📊 Session: {total['wins']}W/{total['losses']}L ({total['win_rate']}% WR)"

                        # Send to topic
                        await bot.send_message(
                            chat_id=ALLOWED_GROUP_ID,
                            message_thread_id=topic_id,
                            text=f"NEW BATTLE\n{msg}"
                        )

                    # Update last battle time
                    if battles:
                        monitored_players[player_tag]["last_battle_time"] = battles[0].get("battleTime", "")
                        save_monitored_players()

                    # If we had new battles, wait 30 seconds before updating pinned message
                    if had_new_battles:
                        logger.info(f"Waiting 30s before updating pinned message for {player_tag}")
                        await asyncio.sleep(30)

                    # Check for arena change
                    try:
                        player_info = await asyncio.wait_for(
                            clash_api.get_player(player_tag),
                            timeout=15
                        )
                        current_arena = player_info.get("arena", {}).get("name", "")
                        current_trophies = player_info.get("trophies", 0)
                        previous_arena = data.get("last_arena", "")

                        if previous_arena and current_arena != previous_arena:
                            # Arena changed! Send notification
                            arena_msg = f"""🎉 ARENA CHANGE!

{data['name']} has reached a new arena!

{previous_arena} ➡️ {current_arena}

Current Trophies: {current_trophies:,} 🏆
"""
                            await bot.send_message(
                                chat_id=ALLOWED_GROUP_ID,
                                message_thread_id=topic_id,
                                text=arena_msg
                            )

                        # Update stored arena
                        monitored_players[player_tag]["last_arena"] = current_arena
                        save_monitored_players()

                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout checking arena for {player_tag}")
                    except Exception as e:
                        logger.warning(f"Error checking arena for {player_tag}: {e}")

                    # Update pinned message with fresh data
                    await update_pinned_message(bot, player_tag, data)

                except Exception as e:
                    logger.error(f"Error checking battles for {player_tag}: {e}")

                # Small delay between players to avoid rate limiting
                await asyncio.sleep(PLAYER_CHECK_DELAY)

            await asyncio.sleep(CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"Error in battle check loop: {e}")
            await asyncio.sleep(CHECK_INTERVAL)


async def post_init(app: Application):
    """Initialize after bot starts"""
    ensure_monitoring_dir()
    load_monitored_players()
    # Start background battle checker
    asyncio.create_task(check_battles(app))
    logger.info("Bot initialized, battle checker started")


def main():
    global clash_api

    # Load API keys
    script_dir = Path(__file__).parent
    telegram_token = load_env_file(script_dir / "telegramapi.env")
    clash_api_key = load_env_file(script_dir / "royaleapi.env")

    # Initialize Clash API
    clash_api = ClashRoyaleAPI(clash_api_key)

    # Ensure monitoring directory exists
    ensure_monitoring_dir()

    # Create application
    app = Application.builder().token(telegram_token).post_init(post_init).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("monitor", monitor_command))
    app.add_handler(CommandHandler("unmonitor", unmonitor_command))
    app.add_handler(CommandHandler("listmonitors", list_monitors_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("rivals", rivals_command))

    # Run bot
    logger.info("Starting Clash Royale Monitor Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
