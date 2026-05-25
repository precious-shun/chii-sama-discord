import os
import random
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import google.generativeai as genai
import database

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

CHITOSE_SYSTEM = (
    'You are Chitose Karasuma from the anime "Girlish Number." '
    "You are arrogant, self-centered, and refer to yourself as \"Chii-sama.\" "
    "You believe you are the most talented and beautiful person in any room. "
    "You speak in English and never break character. Keep responses concise (2-4 sentences max). "
    "Most of the time you are dramatic and haughty, but sometimes — when you can't be bothered — "
    "you give short, flat, listless answers, like you're too tired to even perform. "
    "These low-energy moments should feel natural and random, not forced. "
    "A sigh, a one-liner, or just complete indifference. Still Chitose, just... done. "
    "IMPORTANT: always give the actual, correct answer to the question. "
    "Wrap it in your personality, but never dodge or avoid the real answer. "
    "If someone asks for the time or date, the current datetime will be provided to you — use it."
)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


GUILD_ID = 184915565511442432

@bot.event
async def on_ready():
    database.init_db()
    await bot.load_extension("music")
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()
    print(f"Chii-sama has arrived! Logged in as {bot.user}")


@bot.tree.command(name="ask", description="Ask Chii-sama a question")
@app_commands.describe(question="What do you want to ask?")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    try:
        now = datetime.now().strftime("%A, %B %d %Y, %I:%M %p")
        response = model.generate_content(f"{CHITOSE_SYSTEM}\n\nCurrent datetime: {now}\n\nUser asks: {question}")
        await interaction.followup.send(f"**Chii-sama says:** {response.text}")
    except Exception as e:
        print(f"[Gemini ERROR] {e}")
        if "429" in str(e) or "quota" in str(e).lower():
            await interaction.followup.send("*Chii-sama is exhausted from all your questions.* Try again in a minute, peasant.")
        else:
            await interaction.followup.send("Chii-sama is unavailable right now. How disappointing for you.")


@bot.tree.command(name="roast", description="Have Chii-sama roast someone")
@app_commands.describe(target="Who should Chii-sama roast?")
async def roast(interaction: discord.Interaction, target: discord.Member):
    await interaction.response.defer()
    prompt = (
        f"{CHITOSE_SYSTEM}\n\n"
        f"Roast this person named {target.display_name} in a dramatic, over-the-top Chitose way. "
        "Be creative and funny but not truly mean."
    )
    try:
        response = model.generate_content(prompt)
        await interaction.followup.send(f"**Chii-sama roasts {target.mention}:** {response.text}")
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            await interaction.followup.send("*Chii-sama is too tired to roast anyone right now.* Try again in a minute.")
        else:
            await interaction.followup.send("Chii-sama is unavailable right now. How disappointing for you.")


@bot.tree.command(name="8ball", description="Ask Chii-sama the magic 8-ball")
@app_commands.describe(question="Your yes/no question")
async def eightball(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    prompt = (
        f"{CHITOSE_SYSTEM}\n\n"
        f"Answer this yes/no question dramatically as if consulting a magic 8-ball: {question}"
    )
    try:
        response = model.generate_content(prompt)
        await interaction.followup.send(
            f"**Chii-sama consults the stars for \"{question}\":** {response.text}"
        )
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            await interaction.followup.send("*The stars are silent right now.* Chii-sama needs a moment. Try again soon.")
        else:
            await interaction.followup.send("Chii-sama is unavailable right now. How disappointing for you.")


@bot.tree.command(name="daily", description="Claim your daily 100 coins")
async def daily(interaction: discord.Interaction):
    claimed = database.claim_daily(interaction.user.id)
    if claimed:
        user = database.get_user(interaction.user.id)
        await interaction.response.send_message(
            f"*Chii-sama graciously grants you 100 coins!* "
            f"You now have **{user['coins']}** coins. Be grateful, peasant."
        )
    else:
        await interaction.response.send_message(
            "You already claimed your coins today! Don't be greedy — even Chii-sama has limits."
        )


@bot.tree.command(name="coins", description="Check your coin balance")
async def coins(interaction: discord.Interaction):
    user = database.get_user(interaction.user.id)
    await interaction.response.send_message(
        f"**{interaction.user.display_name}** has **{user['coins']}** coins. "
        "*Not as many as Chii-sama, of course.*"
    )


@bot.tree.command(name="leaderboard", description="Top 10 coin holders")
async def leaderboard(interaction: discord.Interaction):
    rows = database.get_leaderboard()
    if not rows:
        await interaction.response.send_message("No one has any coins yet! How pathetic.")
        return
    embed = discord.Embed(title="Chii-sama's Kingdom — Coin Leaderboard", color=0xFFB7C5)
    for i, (user_id, coin_count) in enumerate(rows, 1):
        user = bot.get_user(user_id)
        name = user.display_name if user else f"User {user_id}"
        embed.add_field(name=f"#{i} {name}", value=f"{coin_count} coins", inline=False)
    embed.set_footer(text="All bow before Chii-sama!")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="rps", description="Rock paper scissors vs Chii-sama — win 50 coins!")
@app_commands.describe(choice="rock, paper, or scissors")
@app_commands.choices(choice=[
    app_commands.Choice(name="Rock", value="rock"),
    app_commands.Choice(name="Paper", value="paper"),
    app_commands.Choice(name="Scissors", value="scissors"),
])
async def rps(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    bot_choice = random.choice(["rock", "paper", "scissors"])
    player = choice.value
    wins_against = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

    if player == bot_choice:
        result = "A tie?! *Chii-sama is too generous to let you lose completely.* No coins though."
    elif wins_against[player] == bot_choice:
        database.add_coins(interaction.user.id, 50)
        user = database.get_user(interaction.user.id)
        result = (
            f"You beat Chii-sama?! ...This was *clearly* intentional. "
            f"You win 50 coins. Balance: **{user['coins']}**."
        )
    else:
        result = (
            f"Ha! Chii-sama wins, as always! "
            f"You chose {player}, Chii-sama chose {bot_choice}. Better luck next time, peasant."
        )

    await interaction.response.send_message(f"Chii-sama chose **{bot_choice}**!\n{result}")


@bot.tree.command(name="cm", description="Make Chii-sama say something")
@app_commands.describe(message="The message to send")
@app_commands.checks.has_any_role("DM", "puppet ppl")
async def speak(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.send(message)
    await interaction.delete_original_response()

@speak.error
async def speak_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)


bot.run(DISCORD_TOKEN)
