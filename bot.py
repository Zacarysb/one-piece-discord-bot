import json
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

TOKEN_FILE = Path(".env")
BOUNTY_FILE = Path("bounties.json")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


import os

def load_env_token():
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token:
        raise ValueError("DISCORD_BOT_TOKEN not found")

    return token

    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DISCORD_BOT_TOKEN="):
                return line.split("=", 1)[1]

    raise ValueError("DISCORD_BOT_TOKEN not found in .env")


def load_bounties():
    if BOUNTY_FILE.exists():
        with open(BOUNTY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_bounties(data):
    with open(BOUNTY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_title(bounty):
    if bounty >= 1_000_000:
        return "Yonko"
    if bounty >= 600_000:
        return "Commander"
    if bounty >= 300_000:
        return "Warlord"
    if bounty >= 100_000:
        return "Supernova"
    return "Rookie"


def get_player_record(bounties, user: discord.Member):
    user_id = str(user.id)

    if user_id not in bounties:
        bounties[user_id] = {
            "name": user.display_name,
            "bounty": 0
        }

    bounties[user_id]["name"] = user.display_name
    return bounties[user_id]


def is_top_player(bounties, user: discord.Member):
    if not bounties:
        return False

    user_id = str(user.id)
    if user_id not in bounties:
        return False

    top_bounty = max(player_data["bounty"] for player_data in bounties.values())
    return bounties[user_id]["bounty"] == top_bounty


def calculate_bonus(match_type, winner_bounty, loser_bounty, loser_is_top_player):
    if match_type == "friendly":
        return 0, 0, 0

    if match_type == "ranked":
        base_bonus = 50_000
        upset_bonus = 0
        king_bonus = 0

        if winner_bounty < loser_bounty:
            upset_bonus = 25_000

        if loser_is_top_player:
            king_bonus = 25_000

        total_bonus = base_bonus + upset_bonus + king_bonus
        return total_bonus, upset_bonus, king_bonus

    return 0, 0, 0


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Sync error: {e}")


@bot.tree.command(name="win", description="Report a match result and update the winner's bounty.")
@app_commands.describe(
    winner="Select the winner",
    loser="Select the loser",
    match_type="friendly or ranked"
)
@app_commands.choices(match_type=[
    app_commands.Choice(name="friendly", value="friendly"),
    app_commands.Choice(name="ranked", value="ranked"),
])
async def win(
    interaction: discord.Interaction,
    winner: discord.Member,
    loser: discord.Member,
    match_type: app_commands.Choice[str]
):
    await interaction.response.defer()

    if winner.id == loser.id:
        await interaction.followup.send("Winner and loser cannot be the same player.")
        return

    bounties = load_bounties()

    winner_record = get_player_record(bounties, winner)
    loser_record = get_player_record(bounties, loser)

    winner_bounty = winner_record["bounty"]
    loser_bounty = loser_record["bounty"]
    loser_is_top_player = is_top_player(bounties, loser)

    bonus, upset_bonus, king_bonus = calculate_bonus(
        match_type.value,
        winner_bounty,
        loser_bounty,
        loser_is_top_player
    )

    winner_record["bounty"] += bonus
    save_bounties(bounties)

    new_bounty = winner_record["bounty"]
    rank_title = get_title(new_bounty)
    base_reward_text = "50,000 Berries" if match_type.value == "ranked" else "0 Berries"

    embed = discord.Embed(
        title="🏴‍☠️ Match Recorded",
        description=f"**{winner.display_name}** defeated **{loser.display_name}**"
    )
    embed.add_field(name="⚔️ Match Type", value=match_type.value.capitalize(), inline=True)
    embed.add_field(name="💰 Base Reward", value=base_reward_text, inline=True)
    embed.add_field(name="🔥 Upset Bonus", value=f"{upset_bonus:,} Berries", inline=True)
    embed.add_field(name="👑 King Bonus", value=f"{king_bonus:,} Berries", inline=True)
    embed.add_field(name="🏆 Total Reward", value=f"{bonus:,} Berries", inline=False)
    embed.add_field(name="💵 New Bounty", value=f"{new_bounty:,} Berries", inline=False)
    embed.add_field(name="🌟 Rank", value=rank_title, inline=True)
    embed.set_footer(text="World Economy News")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="bounty", description="Check a player's current bounty.")
@app_commands.describe(player="Select a player")
async def bounty(interaction: discord.Interaction, player: discord.Member = None):
    bounties = load_bounties()

    if player is None:
        player = interaction.user

    player_record = get_player_record(bounties, player)
    save_bounties(bounties)

    current_bounty = player_record["bounty"]
    title = get_title(current_bounty)

    embed = discord.Embed(
        title="💰 Current Bounty",
        description=f"**{player.display_name}** is worth **{current_bounty:,} Berries**"
    )
    embed.add_field(name="🌟 Rank", value=title, inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="leaderboard", description="Show the top bounty leaderboard.")
async def leaderboard(interaction: discord.Interaction):
    bounties = load_bounties()

    if not bounties:
        await interaction.response.send_message("No bounties recorded yet.")
        return

    sorted_players = sorted(
        bounties.values(),
        key=lambda x: x["bounty"],
        reverse=True
    )

    top_emojis = ["👑", "🌊", "⚔️"]
    top_titles = [
        "Pirate King",
        "Emperor of the Sea",
        "Warlord of the Sea"
    ]

    lines = []

    for i, player_data in enumerate(sorted_players[:10], start=1):
        name = player_data["name"]
        bounty_amount = player_data["bounty"]
        title = get_title(bounty_amount)

        if i <= 3:
            emoji = top_emojis[i - 1]
            special_title = top_titles[i - 1]
            lines.append(
                f"{emoji} **#{i} {special_title} — {name}**\n"
                f"└ {bounty_amount:,} Berries ({title})"
            )
        else:
            lines.append(
                f"🏴‍☠️ **#{i} {name}**\n"
                f"└ {bounty_amount:,} Berries ({title})"
            )

    embed = discord.Embed(
        title="🏆 Grand Line Bounty Leaderboard",
        description="\n\n".join(lines)
    )
    embed.set_footer(text="Marine HQ Rankings")

    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    token = load_env_token()
    bot.run(token)
