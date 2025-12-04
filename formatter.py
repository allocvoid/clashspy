from datetime import datetime
from typing import Optional, List


def format_player_info(player: dict, clan: Optional[dict], chests: dict, monitored_stats: Optional[dict] = None) -> str:
    """Format player information for display"""

    # Basic info
    name = player.get("name", "Unknown")
    tag = player.get("tag", "")
    trophies = player.get("trophies", 0)
    best_trophies = player.get("bestTrophies", 0)
    exp_level = player.get("expLevel", 0)

    # Arena info
    arena = player.get("arena", {})
    arena_name = arena.get("name", "Unknown Arena")

    # Stats
    wins = player.get("wins", 0)
    losses = player.get("losses", 0)
    battles = player.get("battleCount", 0)
    three_crown_wins = player.get("threeCrownWins", 0)

    # Challenge stats
    challenge_max_wins = player.get("challengeMaxWins", 0)
    challenge_cards_won = player.get("challengeCardsWon", 0)

    # Tournament stats
    tournament_cards_won = player.get("tournamentCardsWon", 0)
    tournament_battle_count = player.get("tournamentBattleCount", 0)

    # Card stats
    cards_found = len(player.get("cards", []))

    # Donations
    donations = player.get("donations", 0)
    donations_received = player.get("donationsReceived", 0)
    total_donations = player.get("totalDonations", 0)

    # War stats
    war_day_wins = player.get("warDayWins", 0)
    clan_cards_collected = player.get("clanCardsCollected", 0)

    # Current deck
    current_deck = player.get("currentDeck", [])
    deck_str = ", ".join([card.get("name", "?") for card in current_deck[:8]])

    # Calculate win rate
    win_rate = (wins / battles * 100) if battles > 0 else 0

    # Get current time for "last updated"
    update_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    msg = f"""========================================
Player: {name} ({tag})
Last Updated: {update_time}
========================================

Trophies: {trophies:,} (Best: {best_trophies:,})
Level: {exp_level}
Arena: {arena_name}

Battle Stats (All Time):
- Wins: {wins:,}
- Losses: {losses:,}
- Total Battles: {battles:,}
- Win Rate: {win_rate:.1f}%
- 3-Crown Wins: {three_crown_wins:,}

Challenge Stats:
- Max Wins: {challenge_max_wins}
- Cards Won: {challenge_cards_won:,}

Tournament Stats:
- Battles: {tournament_battle_count:,}
- Cards Won: {tournament_cards_won:,}

Cards Found: {cards_found}

Donations:
- Given: {donations:,}
- Received: {donations_received:,}
- Total Given: {total_donations:,}

War Stats:
- War Day Wins: {war_day_wins:,}
- Clan Cards Collected: {clan_cards_collected:,}

Current Deck:
{deck_str}
"""

    # Add clan info
    player_clan = player.get("clan")
    if player_clan:
        clan_name = player_clan.get("name", "Unknown")
        clan_tag = player_clan.get("tag", "")
        role = player.get("role", "member").replace("elder", "Elder").replace("coLeader", "Co-Leader").replace("leader", "Leader").replace("member", "Member")

        msg += f"""
========================================
Clan: {clan_name} ({clan_tag})
Role: {role}
"""

        if clan:
            clan_trophies = clan.get("clanScore", 0)
            clan_war_trophies = clan.get("clanWarTrophies", 0)
            members = clan.get("members", 0)
            required_trophies = clan.get("requiredTrophies", 0)
            donations_per_week = clan.get("donationsPerWeek", 0)

            msg += f"""- Clan Score: {clan_trophies:,}
- War Trophies: {clan_war_trophies:,}
- Members: {members}/50
- Required Trophies: {required_trophies:,}
- Weekly Donations: {donations_per_week:,}
"""

    # Add upcoming chests
    upcoming = chests.get("items", [])
    if upcoming:
        msg += f"""
========================================
Upcoming Chests:
"""
        for chest in upcoming[:12]:
            chest_name = chest.get("name", "Unknown Chest")
            index = chest.get("index", 0)
            msg += f"  +{index}: {chest_name}\n"

    # Add monitored stats if available
    if monitored_stats and monitored_stats.get("total", {}).get("total", 0) > 0:
        msg += f"""
========================================
MONITORED SESSION STATS:
"""
        total = monitored_stats["total"]
        msg += f"Total: {total['wins']}W / {total['losses']}L / {total['draws']}D ({total['total']} games)\n"
        msg += f"Session Win Rate: {total['win_rate']}%\n"

        if monitored_stats.get("by_mode"):
            msg += "\nBy Game Mode:\n"
            sorted_modes = sorted(
                monitored_stats["by_mode"].items(),
                key=lambda x: x[1]["total"],
                reverse=True
            )
            for mode, mode_stats in sorted_modes[:5]:  # Top 5 modes
                msg += f"  {mode}: {mode_stats['wins']}W/{mode_stats['losses']}L ({mode_stats['win_rate']}%)\n"

    return msg


def format_battle(battle: dict) -> str:
    """Format a single battle for display"""

    battle_type = battle.get("type", "Unknown")
    game_mode = battle.get("gameMode", {}).get("name", "Unknown Mode")
    battle_time = battle.get("battleTime", "")

    # Parse battle time
    if battle_time:
        try:
            dt = datetime.strptime(battle_time, "%Y%m%dT%H%M%S.%fZ")
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except:
            time_str = battle_time
    else:
        time_str = "Unknown"

    # Team info
    team = battle.get("team", [{}])[0]
    team_name = team.get("name", "Unknown")
    team_tag = team.get("tag", "")
    team_crowns = team.get("crowns", 0)
    team_trophies = team.get("startingTrophies", 0)
    team_trophy_change = team.get("trophyChange", 0)
    team_cards = team.get("cards", [])

    # Opponent info
    opponent = battle.get("opponent", [{}])[0]
    opp_name = opponent.get("name", "Unknown")
    opp_tag = opponent.get("tag", "")
    opp_crowns = opponent.get("crowns", 0)
    opp_trophies = opponent.get("startingTrophies", 0)
    opp_cards = opponent.get("cards", [])

    # Determine result
    if team_crowns > opp_crowns:
        result = "VICTORY"
        result_emoji = "🏆"
    elif team_crowns < opp_crowns:
        result = "DEFEAT"
        result_emoji = "💀"
    else:
        result = "DRAW"
        result_emoji = "🤝"

    # Format trophy change
    trophy_str = ""
    if team_trophy_change > 0:
        trophy_str = f" (+{team_trophy_change})"
    elif team_trophy_change < 0:
        trophy_str = f" ({team_trophy_change})"

    # Format decks
    team_deck = ", ".join([f"{c.get('name', '?')}" for c in team_cards[:8]])
    opp_deck = ", ".join([f"{c.get('name', '?')}" for c in opp_cards[:8]])

    # Arena
    arena = battle.get("arena", {}).get("name", "Unknown Arena")

    msg = f"""========================================
{result_emoji} {result}{trophy_str}
========================================
Mode: {game_mode}
Arena: {arena}
Time: {time_str}

{team_name} ({team_tag})
- Trophies: {team_trophies:,}
- Crowns: {team_crowns}
- Deck: {team_deck}

VS

{opp_name} ({opp_tag})
- Trophies: {opp_trophies:,}
- Crowns: {opp_crowns}
- Deck: {opp_deck}
"""

    return msg


def format_battle_short(battle: dict, player_tag: str) -> str:
    """Format a battle notification (shorter version)"""

    game_mode = battle.get("gameMode", {}).get("name", "Unknown Mode")
    battle_time = battle.get("battleTime", "")

    if battle_time:
        try:
            dt = datetime.strptime(battle_time, "%Y%m%dT%H%M%S.%fZ")
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except:
            time_str = battle_time
    else:
        time_str = "Unknown"

    # Find the monitored player in team or opponent
    team = battle.get("team", [{}])
    opponent = battle.get("opponent", [{}])

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

    player_crowns = player_data.get("crowns", 0)
    enemy_crowns = enemy_data.get("crowns", 0)
    trophy_change = player_data.get("trophyChange", 0)

    # Determine result
    if player_crowns > enemy_crowns:
        result = "🏆 VICTORY"
    elif player_crowns < enemy_crowns:
        result = "💀 DEFEAT"
    else:
        result = "🤝 DRAW"

    trophy_str = ""
    if trophy_change > 0:
        trophy_str = f" (+{trophy_change})"
    elif trophy_change < 0:
        trophy_str = f" ({trophy_change})"

    enemy_name = enemy_data.get("name", "Unknown")
    enemy_tag = enemy_data.get("tag", "Unknown")
    enemy_trophies = enemy_data.get("startingTrophies", 0)

    player_deck = [c.get("name", "?") for c in player_data.get("cards", [])[:8]]
    enemy_deck = [c.get("name", "?") for c in enemy_data.get("cards", [])[:8]]

    msg = f"""Time: {time_str}

{result}{trophy_str}
Mode: {game_mode}

Score: {player_crowns} - {enemy_crowns}

Opponent: {enemy_name}
Tag: {enemy_tag}
Trophies: {enemy_trophies:,}

Your Deck:
{', '.join(player_deck)}

Enemy Deck:
{', '.join(enemy_deck)}
"""

    return msg


def format_rivals_list(rivals: List[dict], player_name: str = "Player") -> str:
    """Format a list of repeat opponents (rivals)"""
    if not rivals:
        return f"No repeat opponents found for {player_name}.\nPlay more games to track rivalries!"

    msg = f"""========================================
RIVALS - Repeat Opponents for {player_name}
========================================

"""
    for i, rival in enumerate(rivals[:15], 1):  # Top 15 rivals
        name = rival.get("name", "Unknown")
        tag = rival.get("tag", "")
        total = rival.get("total", 0)
        wins = rival.get("wins", 0)
        losses = rival.get("losses", 0)
        draws = rival.get("draws", 0)
        win_rate = rival.get("win_rate", 0)

        # Determine rivalry status
        if wins > losses:
            status = "Dominating"
        elif losses > wins:
            status = "Struggling"
        else:
            status = "Even"

        msg += f"{i}. {name} ({tag})\n"
        msg += f"   Matches: {total} | Record: {wins}W/{losses}L/{draws}D\n"
        msg += f"   Win Rate: {win_rate}% | Status: {status}\n"

        # Show game modes if multiple
        by_mode = rival.get("by_mode", {})
        if len(by_mode) > 1:
            modes_str = ", ".join([f"{mode}: {stats['total']}" for mode, stats in sorted(by_mode.items(), key=lambda x: x[1]['total'], reverse=True)[:3]])
            msg += f"   Modes: {modes_str}\n"

        msg += "\n"

    total_rivals = len(rivals)
    if total_rivals > 15:
        msg += f"... and {total_rivals - 15} more rivals\n"

    return msg


def format_opponent_detail(opponent: dict) -> str:
    """Format detailed stats against a specific opponent"""
    if not opponent:
        return "No history found against this opponent."

    name = opponent.get("name", "Unknown")
    tag = opponent.get("tag", "")
    total = opponent.get("total", 0)
    wins = opponent.get("wins", 0)
    losses = opponent.get("losses", 0)
    draws = opponent.get("draws", 0)
    win_rate = opponent.get("win_rate", 0)

    msg = f"""========================================
HEAD-TO-HEAD: vs {name}
========================================

Opponent Tag: {tag}
Total Matches: {total}

Record: {wins}W / {losses}L / {draws}D
Win Rate: {win_rate}%

"""

    # Stats by game mode
    by_mode = opponent.get("by_mode", {})
    if by_mode:
        msg += "BY GAME MODE:\n"
        msg += "-" * 20 + "\n"
        sorted_modes = sorted(by_mode.items(), key=lambda x: x[1]["total"], reverse=True)
        for mode, stats in sorted_modes:
            msg += f"\n{mode}:\n"
            msg += f"  Record: {stats['wins']}W / {stats['losses']}L / {stats['draws']}D\n"
            msg += f"  Games: {stats['total']} | Win Rate: {stats['win_rate']}%\n"

    # Match history (last 10)
    battles = opponent.get("battles", [])
    if battles:
        msg += "\n" + "=" * 40 + "\n"
        msg += "RECENT MATCH HISTORY:\n"
        msg += "-" * 20 + "\n"

        # Show last 10 matches (most recent first)
        for battle in reversed(battles[-10:]):
            result = battle.get("result", "unknown")
            if result == "win":
                result_icon = "W"
            elif result == "loss":
                result_icon = "L"
            else:
                result_icon = "D"

            mode = battle.get("mode", "Unknown")
            time_str = battle.get("time_formatted", "Unknown time")
            player_crowns = battle.get("player_crowns", 0)
            enemy_crowns = battle.get("enemy_crowns", 0)

            msg += f"[{result_icon}] {player_crowns}-{enemy_crowns} | {mode} | {time_str}\n"

    return msg


def format_repeat_opponent_alert(opponent: dict, is_new_battle: bool = True) -> str:
    """Format an alert when facing a repeat opponent"""
    name = opponent.get("name", "Unknown")
    total = opponent.get("total", 0)
    wins = opponent.get("wins", 0)
    losses = opponent.get("losses", 0)
    win_rate = opponent.get("win_rate", 0)

    if is_new_battle:
        # This is shown BEFORE the current battle result is recorded
        previous_matches = total
        msg = f"RIVAL ALERT! You've faced {name} {previous_matches} time(s) before!\n"
        msg += f"Previous Record: {wins}W/{losses}L ({win_rate}% WR)"
    else:
        # This is shown AFTER the current battle result is recorded
        msg = f"RIVAL MATCH! {total} total matches vs {name}\n"
        msg += f"Record: {wins}W/{losses}L ({win_rate}% WR)"

    return msg
