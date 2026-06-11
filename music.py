import aiohttp
import discord
import wavelink
from discord import app_commands
from discord.ext import commands

PUBLIC_NODES_URL = "https://lavalink-list.ajieblogs.eu.org/All"


async def connect_lavalink(bot: commands.Bot) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(PUBLIC_NODES_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    print(f"[Music] Node API returned {resp.status}")
                    return False
                raw = await resp.json()
    except Exception as e:
        print(f"[Music] Node fetch failed: {e}")
        return False

    if not isinstance(raw, list):
        return False

    v4 = [n for n in raw if isinstance(n, dict) and n.get("version") == "v4"]
    secure = [n for n in v4 if n.get("secure") is True]
    candidates = (secure or v4)[:8]

    for i, nd in enumerate(candidates):
        host = str(nd.get("host", "")).strip()
        port = nd.get("port")
        password = str(nd.get("password", "")).strip()
        ssl = nd.get("secure") is True

        if not host or not isinstance(port, int) or not password:
            continue

        scheme = "wss" if ssl else "ws"
        uri = f"{scheme}://{host}:{port}"
        try:
            node = wavelink.Node(identifier=f"pub{i}", uri=uri, password=password)
            await wavelink.Pool.connect(nodes=[node], client=bot)
            print(f"[Music] Connected to Lavalink: {uri}")
            return True
        except Exception as e:
            print(f"[Music] Node {uri} failed: {e}")

    print("[Music] No working Lavalink node found.")
    return False


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        ok = await connect_lavalink(self.bot)
        print(f"[Music] Lavalink connected: {ok}")

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        await player.disconnect()

    def _player(self, guild: discord.Guild) -> "wavelink.Player | None":
        return guild.voice_client  # type: ignore

    @app_commands.command(name="play", description="Play a song from YouTube")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel first, peasant.")
            return

        player = self._player(interaction.guild)
        if not player:
            player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            player.autoplay = wavelink.AutoPlayMode.partial
        elif player.channel != interaction.user.voice.channel:
            await player.move_to(interaction.user.voice.channel)

        try:
            tracks = await wavelink.Playable.search(query)
        except Exception as e:
            await interaction.followup.send(f"**[DEBUG] Search error:** `{type(e).__name__}: {e}`")
            return

        node = wavelink.Pool.get_node()
        node_info = f"`{node.uri}`" if node else "`no node connected`"
        await interaction.followup.send(f"**[DEBUG]** Node: {node_info} | Query: `{query}` | Results: `{len(tracks) if tracks else 0}`")

        if not tracks:
            await interaction.followup.send("*Chii-sama couldn't find that.* Try a different search.")
            return

        if isinstance(tracks, wavelink.Playlist):
            for t in tracks.tracks:
                t.extras = wavelink.ExtrasNamespace({"requester": interaction.user.display_name})
                await player.queue.put_wait(t)
            reply = f"Added playlist **{tracks.name}** ({len(tracks.tracks)} tracks) to the queue."
        else:
            track = tracks[0]
            track.extras = wavelink.ExtrasNamespace({"requester": interaction.user.display_name})
            await player.queue.put_wait(track)
            reply = f"Added to queue: **{track.title}**"

        if not player.playing and not player.paused:
            next_t = player.queue.get()
            await player.play(next_t)
            reply = f"*Chii-sama graces you with music.* Now playing: **{next_t.title}**"

        await interaction.followup.send(reply)

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        player = self._player(interaction.guild)
        if player and player.playing:
            await player.pause(True)
            await interaction.response.send_message("*Chii-sama pauses for dramatic effect.*")
        else:
            await interaction.response.send_message("Nothing is playing.")

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        player = self._player(interaction.guild)
        if player and player.paused:
            await player.pause(False)
            await interaction.response.send_message("*The performance continues!*")
        else:
            await interaction.response.send_message("Nothing is paused.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        player = self._player(interaction.guild)
        if not player or not player.current:
            await interaction.response.send_message("Nothing is playing right now.")
            return
        await player.skip(force=True)
        await interaction.response.send_message("*Chii-sama skips this inferior track.*")

    @app_commands.command(name="stop", description="Stop music and leave the voice channel")
    async def stop(self, interaction: discord.Interaction):
        player = self._player(interaction.guild)
        if player:
            await player.disconnect()
        await interaction.response.send_message("*Chii-sama has left the stage. You're welcome.*")

    @app_commands.command(name="leave", description="Chii-sama leaves the voice channel")
    async def leave(self, interaction: discord.Interaction):
        player = self._player(interaction.guild)
        if not player:
            await interaction.response.send_message("I'm not even in a voice channel.")
            return
        await player.disconnect()
        await interaction.response.send_message("*Chii-sama has left. You're welcome.*")

    @app_commands.command(name="queue", description="Show the current music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        player = self._player(interaction.guild)
        if not player or (not player.current and player.queue.is_empty):
            await interaction.response.send_message("The queue is empty. Request something worthy of Chii-sama!")
            return

        embed = discord.Embed(title="Chii-sama's Playlist", color=0xFFB7C5)
        if player.current:
            t = player.current
            requester = getattr(t.extras, "requester", "Unknown")
            embed.add_field(
                name="Now Playing",
                value=f"**[{t.title}](https://www.youtube.com/watch?v={t.identifier})**\nRequested by {requester}",
                inline=False,
            )
        if not player.queue.is_empty:
            lines = [
                f"{i+1}. **{s.title}** — {getattr(s.extras, 'requester', 'Unknown')}"
                for i, s in enumerate(player.queue)
            ]
            embed.add_field(name="Up Next", value="\n".join(lines[:10]), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show what's currently playing")
    async def nowplaying(self, interaction: discord.Interaction):
        player = self._player(interaction.guild)
        if not player or not player.current:
            await interaction.response.send_message("Nothing is playing right now.")
            return

        t = player.current
        requester = getattr(t.extras, "requester", "Unknown")
        embed = discord.Embed(title="Now Playing", color=0xFFB7C5)
        embed.add_field(
            name=t.title,
            value=f"[Open link](https://www.youtube.com/watch?v={t.identifier}) | Requested by {requester}",
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
