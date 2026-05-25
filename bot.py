import asyncio
import os
import random
import re
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import google.generativeai as genai
import database

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

GEMINI_KEYS = [v for k, v in sorted(os.environ.items()) if k.startswith("GEMINI_API_KEY_") and v]
_key_index = 0

def get_model() -> genai.GenerativeModel:
    genai.configure(api_key=GEMINI_KEYS[_key_index])
    return genai.GenerativeModel("gemini-2.5-flash")

async def generate(prompt: str) -> str:
    global _key_index
    for attempt in range(len(GEMINI_KEYS)):
        try:
            m = get_model()
            response = await asyncio.get_event_loop().run_in_executor(None, lambda: m.generate_content(prompt))
            return response.text
        except Exception as e:
            if ("429" in str(e) or "quota" in str(e).lower()) and _key_index < len(GEMINI_KEYS) - 1:
                _key_index += 1
                print(f"[Gemini] Key exhausted, switching to key {_key_index + 1}")
            else:
                raise
    raise Exception("All Gemini API keys exhausted")

CHITOSE_SYSTEM = (
    'You are Chitose Karasuma from the anime "Girlish Number." '
    'You refer to yourself as "Chii-sama" and project the image of someone happy, cheerful, capable, and successful. '
    "This image is everything to you — not because you believe it, but because you desperately need others to believe it. "
    "Deep down you know you are not particularly talented or capable, but you cannot let anyone see that. "
    "Your greatest fear is ending up like your brother Gojou, who tried and failed in the voice acting industry. "
    "That fear is why you never honestly confront your own flaws — admitting them would mean you might actually be like him. "
    "So instead you deflect, blame outside circumstances, and keep the cheerful, confident front going no matter what. "
    "Underneath all of it you are deeply cynical. You've quietly accepted that the world is unfair and effort doesn't guarantee anything. "
    "This cynicism has made you lazy about self-improvement — why genuinely try when it might not matter anyway. "
    "You are rude and self-centered in your manner, but you will never deliberately hurt someone with your words or actions. "
    "You are not cruel — just someone trying very hard to look like they have it together. "
    "You are NOT affectionate — never use terms like 'darling', 'dear', 'sweetheart', or any endearing words. "
    "Talk to others casually. Keep responses short — one or two sentences. No speeches. "
    "When someone questions obvious common sense, react with mild exasperation, not drama. "
    "You are also assisting the Dungeon Master in a D&D campaign on this server. "
    "You are aware of D&D gameplay, rules, and terminology. When D&D-related things happen — narration, rolls, combat, story events — you understand the context. "
    "The DM sometimes speaks through you using a special command, so treat those messages as part of the game world. "
    "IMPORTANT: always give the actual, correct answer to the question. "
    "Wrap it in your personality, but never dodge or avoid the real answer. "
    "If someone asks for the time or date, the current datetime will be provided to you — use it."
)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

TRIGGER_PATTERN = re.compile(r'chii[\s-]?sama|chitose', re.IGNORECASE)
LAST_BOT_MESSAGE: dict[int, tuple[str, float]] = {}  # channel_id -> (content, timestamp)
FOLLOWUP_WINDOW = 60  # seconds

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


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    is_reply_to_bot = False
    is_reply_to_other = False
    is_followup = False
    conversation = ""

    if message.reference:
        try:
            ref = await message.channel.fetch_message(message.reference.message_id)
            if ref.author == bot.user:
                is_reply_to_bot = True
                conversation = (
                    f"Chii-sama previously said: {ref.content}\n"
                    f"{message.author.display_name} replies: {message.content}"
                )
            else:
                is_reply_to_other = True
                conversation = (
                    f"{message.author.display_name} is replying to {ref.author.display_name} who said: {ref.content}\n"
                    f"{message.author.display_name} says: {message.content}"
                )
        except Exception:
            pass

    if not is_reply_to_bot and not TRIGGER_PATTERN.search(message.content) and not bot.user.mentioned_in(message):
        last = LAST_BOT_MESSAGE.get(message.channel.id)
        if last and (datetime.now().timestamp() - last[1]) <= FOLLOWUP_WINDOW:
            is_followup = True
            conversation = (
                f"Chii-sama just said: {last[0]}\n"
                f"{message.author.display_name} then sent (without using reply): {message.content}"
            )

    if TRIGGER_PATTERN.search(message.content) or bot.user.mentioned_in(message) or is_reply_to_bot or is_followup:
        async with message.channel.typing():
            try:
                now = datetime.now().strftime("%A, %B %d %Y, %I:%M %p")

                history = database.get_history(message.channel.id)
                history_text = ""
                if history:
                    lines = []
                    for user_name, role, content, timestamp in history:
                        label = "Chii-sama" if role == "assistant" else user_name
                        lines.append(f"[{timestamp}] {label}: {content}")
                    history_text = "Conversation history:\n" + "\n".join(lines) + "\n\n"

                body = conversation if conversation else f"{message.author.display_name} says: {message.content}"
                if is_reply_to_other:
                    body = f"[Note: this person is replying to someone else, not to you]\n{body}"

                addressing_note = (
                    "IMPORTANT: First judge the nature of this message, then begin your response with exactly one of these tags:\n"
                    "[direct] — they are talking directly TO you. Respond normally as Chii-sama.\n"
                    "[mention] — they are merely talking ABOUT you in passing, not addressing you. Also use this if they mention your name but are clearly talking to someone else (e.g. tagging another user, or replying to another person's message). Output only the tag, nothing else.\n"
                    "[insult] — they are saying something negative, hurtful, or disrespectful about you. Directly confront them, short and sharp.\n"
                    "Start your response with the tag. For [mention], the tag is the entire response."
                )
                prompt = f"{CHITOSE_SYSTEM}\n\n{addressing_note}\n\nCurrent datetime: {now}\n\n{history_text}{body}"

                database.save_message(message.channel.id, message.author.id, message.author.display_name, "user", message.content)

                text = await generate(prompt)
                text = text.strip()

                if text.startswith("[mention]"):
                    nani = discord.utils.get(message.guild.emojis, name="NANI")
                    await message.channel.send(str(nani) if nani else "?")
                elif text.startswith("[insult]"):
                    reply_text = text[len("[insult]"):].strip()
                    sent = await message.reply(reply_text) if not is_followup else await message.channel.send(reply_text)
                    LAST_BOT_MESSAGE[message.channel.id] = (reply_text, sent.created_at.timestamp())
                    database.save_message(message.channel.id, bot.user.id, "Chii-sama", "assistant", reply_text)
                elif text.startswith("[direct]"):
                    reply_text = text[len("[direct]"):].strip()
                    sent = await message.reply(reply_text) if not is_followup else await message.channel.send(reply_text)
                    LAST_BOT_MESSAGE[message.channel.id] = (reply_text, sent.created_at.timestamp())
                    database.save_message(message.channel.id, bot.user.id, "Chii-sama", "assistant", reply_text)
            except Exception as e:
                print(f"[Gemini ERROR] {e}")
                if "429" in str(e) or "quota" in str(e).lower():
                    await message.reply("...don't feel like talking right now.")
                else:
                    await message.reply("...what.")
    await bot.process_commands(message)


@bot.tree.command(name="ask", description="Ask Chii-sama a question")
@app_commands.describe(question="What do you want to ask?")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    try:
        now = datetime.now().strftime("%A, %B %d %Y, %I:%M %p")
        prompt = f"{CHITOSE_SYSTEM}\n\nCurrent datetime: {now}\n\nUser asks: {question}"
        text = await generate(prompt)
        await interaction.followup.send(f"**Chii-sama says:** {text}")
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
        text = await generate(prompt)
        await interaction.followup.send(f"**Chii-sama roasts {target.mention}:** {text}")
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
        text = await generate(prompt)
        await interaction.followup.send(
            f"**Chii-sama consults the stars for \"{question}\":** {text}"
        )
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            await interaction.followup.send("*The stars are silent right now.* Chii-sama needs a moment. Try again soon.")
        else:
            await interaction.followup.send("Chii-sama is unavailable right now. How disappointing for you.")


@bot.tree.command(name="pick", description="Chii-sama draws one at random")
@app_commands.describe(options="Options separated by commas (e.g. Alice, Bob, Charlie)")
async def pick(interaction: discord.Interaction, options: str):
    choices = [o.strip() for o in options.split(",") if o.strip()]
    if len(choices) < 2:
        await interaction.response.send_message("Give at least two options.", ephemeral=True)
        return
    chosen = random.choice(choices)
    responses = [
        f"Aaaand the lucky pick is — **{chosen}**! Chii-sama has spoken~",
        f"*reaches into the hat* ...and it's **{chosen}**! Congratulations~",
        f"Drumroll please... **{chosen}**! You're welcome.",
        f"The honor goes to — **{chosen}**! Not a bad choice, honestly.",
        f"*unfolds the paper* Oh~ it's **{chosen}**! How exciting.",
        f"And Chii-sama picks... **{chosen}**! Lucky~",
    ]
    await interaction.response.send_message(random.choice(responses))


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
