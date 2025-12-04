import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


MONITORING_DIR = Path(__file__).parent / "monitoring"


def ensure_monitoring_dir():
    """Ensure the monitoring directory exists"""
    MONITORING_DIR.mkdir(exist_ok=True)


def get_player_file(player_tag: str) -> Path:
    """Get the battle log file path for a player"""
    clean_tag = player_tag.replace("#", "").upper()
    return MONITORING_DIR / f"{clean_tag}.json"


def load_player_data(player_tag: str) -> dict:
    """Load player battle data from file"""
    filepath = get_player_file(player_tag)
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "player_tag": player_tag,
        "battles": [],
        "stats": {},
        "opponent_stats": {}
    }


def save_player_data(player_tag: str, data: dict):
    """Save player battle data to file"""
    ensure_monitoring_dir()
    filepath = get_player_file(player_tag)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def categorize_game_mode(battle: dict) -> str:
    """Categorize a battle into a game mode category"""
    battle_type = battle.get("type", "").lower()
    game_mode = battle.get("gameMode", {}).get("name", "").lower()

    # Check for 2v2
    if "2v2" in game_mode or "2v2" in battle_type:
        return "2v2"

    # Check for friendly battles
    if "friendly" in battle_type or "friendly" in game_mode:
        return "Friendly"

    # Check for challenges
    if "challenge" in battle_type or "challenge" in game_mode:
        return "Challenge"

    # Check for tournaments
    if "tournament" in battle_type or "tournament" in game_mode:
        return "Tournament"

    # Check for clan war
    if "clanwar" in battle_type or "war" in game_mode or "clanwar" in game_mode:
        return "Clan War"

    # Check for party modes
    if "party" in game_mode:
        return "Party Mode"

    # Check for ladder (Path of Legends / Trophy Road)
    if "pathoflegend" in battle_type or "ladder" in battle_type:
        return "Ladder"

    # Default to the game mode name or 1v1
    if game_mode:
        # Capitalize properly
        return battle.get("gameMode", {}).get("name", "1v1")

    return "1v1"


def determine_battle_result(battle: dict, player_tag: str) -> str:
    """Determine if the player won, lost, or drew"""
    team = battle.get("team", [])
    opponent = battle.get("opponent", [])

    player_crowns = 0
    enemy_crowns = 0

    # Find player in team or opponent
    for t in team:
        if t.get("tag", "").upper() == player_tag.upper():
            player_crowns = t.get("crowns", 0)
            enemy_crowns = opponent[0].get("crowns", 0) if opponent else 0
            break
    else:
        for o in opponent:
            if o.get("tag", "").upper() == player_tag.upper():
                player_crowns = o.get("crowns", 0)
                enemy_crowns = team[0].get("crowns", 0) if team else 0
                break

    if player_crowns > enemy_crowns:
        return "win"
    elif player_crowns < enemy_crowns:
        return "loss"
    else:
        return "draw"


def extract_battle_info(battle: dict, player_tag: str) -> dict:
    """Extract relevant battle information for logging"""
    team = battle.get("team", [])
    opponent = battle.get("opponent", [])

    player_data = None
    enemy_data = None

    for t in team:
        if t.get("tag", "").upper() == player_tag.upper():
            player_data = t
            enemy_data = opponent[0] if opponent else {}
            break

    if not player_data:
        for o in opponent:
            if o.get("tag", "").upper() == player_tag.upper():
                player_data = o
                enemy_data = team[0] if team else {}
                break

    if not player_data:
        player_data = team[0] if team else {}
        enemy_data = opponent[0] if opponent else {}

    battle_time = battle.get("battleTime", "")
    try:
        dt = datetime.strptime(battle_time, "%Y%m%dT%H%M%S.%fZ")
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        time_str = battle_time

    return {
        "battle_time": battle_time,
        "time_formatted": time_str,
        "game_mode": battle.get("gameMode", {}).get("name", "Unknown"),
        "game_mode_category": categorize_game_mode(battle),
        "type": battle.get("type", "Unknown"),
        "arena": battle.get("arena", {}).get("name", "Unknown"),
        "result": determine_battle_result(battle, player_tag),
        "player": {
            "name": player_data.get("name", "Unknown"),
            "tag": player_data.get("tag", ""),
            "crowns": player_data.get("crowns", 0),
            "trophies": player_data.get("startingTrophies", 0),
            "trophy_change": player_data.get("trophyChange", 0),
            "deck": [c.get("name", "?") for c in player_data.get("cards", [])[:8]]
        },
        "enemy": {
            "name": enemy_data.get("name", "Unknown"),
            "tag": enemy_data.get("tag", ""),
            "crowns": enemy_data.get("crowns", 0),
            "trophies": enemy_data.get("startingTrophies", 0),
            "deck": [c.get("name", "?") for c in enemy_data.get("cards", [])[:8]]
        }
    }


def add_battle(player_tag: str, battle: dict) -> dict:
    """Add a battle to the player's log and return updated stats"""
    data = load_player_data(player_tag)

    battle_info = extract_battle_info(battle, player_tag)

    # Check if battle already exists (by battle_time)
    existing_times = [b.get("battle_time") for b in data["battles"]]
    if battle_info["battle_time"] not in existing_times:
        data["battles"].append(battle_info)
        # Keep only last 100 battles to avoid file bloat
        data["battles"] = data["battles"][-100:]

    # Recalculate stats
    data["stats"] = calculate_stats(data["battles"])
    data["opponent_stats"] = calculate_opponent_stats(data["battles"])

    save_player_data(player_tag, data)
    return data["stats"]


def calculate_stats(battles: list) -> dict:
    """Calculate win/loss statistics per game mode"""
    stats = {
        "total": {"wins": 0, "losses": 0, "draws": 0, "total": 0},
        "by_mode": {}
    }

    for battle in battles:
        result = battle.get("result", "unknown")
        mode = battle.get("game_mode_category", "Unknown")

        # Initialize mode stats if needed
        if mode not in stats["by_mode"]:
            stats["by_mode"][mode] = {"wins": 0, "losses": 0, "draws": 0, "total": 0}

        # Update counts
        stats["total"]["total"] += 1
        stats["by_mode"][mode]["total"] += 1

        if result == "win":
            stats["total"]["wins"] += 1
            stats["by_mode"][mode]["wins"] += 1
        elif result == "loss":
            stats["total"]["losses"] += 1
            stats["by_mode"][mode]["losses"] += 1
        elif result == "draw":
            stats["total"]["draws"] += 1
            stats["by_mode"][mode]["draws"] += 1

    # Calculate win rates
    if stats["total"]["total"] > 0:
        stats["total"]["win_rate"] = round(stats["total"]["wins"] / stats["total"]["total"] * 100, 1)
    else:
        stats["total"]["win_rate"] = 0.0

    for mode in stats["by_mode"]:
        mode_stats = stats["by_mode"][mode]
        if mode_stats["total"] > 0:
            mode_stats["win_rate"] = round(mode_stats["wins"] / mode_stats["total"] * 100, 1)
        else:
            mode_stats["win_rate"] = 0.0

    return stats


def calculate_opponent_stats(battles: list) -> dict:
    """Calculate statistics per opponent (for tracking repeat matchups)"""
    opponents = {}

    for battle in battles:
        enemy = battle.get("enemy", {})
        enemy_tag = enemy.get("tag", "").upper()
        enemy_name = enemy.get("name", "Unknown")

        if not enemy_tag:
            continue

        # Initialize opponent stats if needed
        if enemy_tag not in opponents:
            opponents[enemy_tag] = {
                "name": enemy_name,
                "tag": enemy_tag,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "total": 0,
                "by_mode": {},
                "battles": []
            }

        opp = opponents[enemy_tag]
        opp["name"] = enemy_name  # Update name in case it changed
        opp["total"] += 1

        result = battle.get("result", "unknown")
        if result == "win":
            opp["wins"] += 1
        elif result == "loss":
            opp["losses"] += 1
        elif result == "draw":
            opp["draws"] += 1

        # Track by game mode
        mode = battle.get("game_mode_category", "Unknown")
        if mode not in opp["by_mode"]:
            opp["by_mode"][mode] = {"wins": 0, "losses": 0, "draws": 0, "total": 0}

        opp["by_mode"][mode]["total"] += 1
        if result == "win":
            opp["by_mode"][mode]["wins"] += 1
        elif result == "loss":
            opp["by_mode"][mode]["losses"] += 1
        elif result == "draw":
            opp["by_mode"][mode]["draws"] += 1

        # Store battle reference (time and result for history)
        opp["battles"].append({
            "time": battle.get("battle_time", ""),
            "time_formatted": battle.get("time_formatted", ""),
            "result": result,
            "mode": mode,
            "player_crowns": battle.get("player", {}).get("crowns", 0),
            "enemy_crowns": enemy.get("crowns", 0)
        })

    # Calculate win rates for each opponent
    for tag, opp in opponents.items():
        if opp["total"] > 0:
            opp["win_rate"] = round(opp["wins"] / opp["total"] * 100, 1)
        else:
            opp["win_rate"] = 0.0

        # Calculate win rates by mode
        for mode, mode_stats in opp["by_mode"].items():
            if mode_stats["total"] > 0:
                mode_stats["win_rate"] = round(mode_stats["wins"] / mode_stats["total"] * 100, 1)
            else:
                mode_stats["win_rate"] = 0.0

    return opponents


def get_repeat_opponents(player_tag: str, min_matches: int = 2) -> list:
    """Get opponents faced multiple times, sorted by number of matches"""
    data = load_player_data(player_tag)
    opponent_stats = data.get("opponent_stats", {})

    # Filter to opponents with at least min_matches
    repeat_opponents = [
        opp for opp in opponent_stats.values()
        if opp.get("total", 0) >= min_matches
    ]

    # Sort by total matches (most frequent first)
    repeat_opponents.sort(key=lambda x: x.get("total", 0), reverse=True)

    return repeat_opponents


def get_opponent_history(player_tag: str, opponent_tag: str) -> Optional[dict]:
    """Get the full history against a specific opponent"""
    data = load_player_data(player_tag)
    opponent_stats = data.get("opponent_stats", {})
    return opponent_stats.get(opponent_tag.upper())


def get_player_stats(player_tag: str) -> dict:
    """Get current stats for a player"""
    data = load_player_data(player_tag)
    if not data.get("stats"):
        data["stats"] = calculate_stats(data.get("battles", []))
    return data["stats"]


def format_stats_message(stats: dict) -> str:
    """Format stats for display in Telegram"""
    if not stats or stats["total"]["total"] == 0:
        return "No battle data recorded yet."

    total = stats["total"]
    msg = f"""📊 MONITORED BATTLE STATISTICS
========================================
Total: {total['wins']}W / {total['losses']}L / {total['draws']}D ({total['total']} games)
Win Rate: {total['win_rate']}%

📋 BY GAME MODE:
"""

    # Sort modes by total games played
    sorted_modes = sorted(
        stats["by_mode"].items(),
        key=lambda x: x[1]["total"],
        reverse=True
    )

    for mode, mode_stats in sorted_modes:
        msg += f"\n{mode}:\n"
        msg += f"  {mode_stats['wins']}W / {mode_stats['losses']}L / {mode_stats['draws']}D\n"
        msg += f"  Win Rate: {mode_stats['win_rate']}% ({mode_stats['total']} games)\n"

    return msg
