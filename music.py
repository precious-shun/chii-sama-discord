import asyncio
import re
from collections import deque

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

INVIDIOUS_INSTANCES = [
    'https://inv.tux.pizza',
    'https://invidious.privacyredirect.com',
    'https://yt.artemislena.eu',
    'https://invidious.slipfox.xyz',
]

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

YT_ID_PATTERN = re.compile(
    r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})'
)


class Song:
    def __init__(self, url: str, title: str, video_id: str, requester: str):
        self.url = url
        self.title = title
        self.webpage_url = f"https://www.youtube.com/watch?v={video_id}"
        self.requester = requester


class GuildPlayer:
    def __init__(self):
        self.queue: deque[Song] = deque()
        self.current: Song | None = None
        self.voice_client: discord.VoiceClient | None = None


_players: dict[int, GuildPlayer] = {}


def get_player(guild_id: int) -> GuildPlayer:
    if guild_id not in _players:
        _players[guild_id] = GuildPlayer()
    return _players[guild_id]


async def _try_instance(session: aiohttp.ClientSession, instance: str, path: str, params: dict) -> dict | list | None:
    try:
        async with session.get(
            f"{instance}{path}",
            params=params,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        print(f"[Music] Invidious {instance} error: {e}")
    return None


async def _invidious_get(path: str, params: dict) -> dict | list | None:
    async with aiohttp.ClientSession() as session:
        tasks = [_try_instance(session, inst, path, params) for inst in INVIDIOUS_INSTANCES]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result is not None:
                return result
    return None


async def resolve_query(query: str) -> tuple[str, str] | None:
    """Returns (video_id, title) or None."""
    match = YT_ID_PATTERN.search(query)
    if match:
        video_id = match.group(1)
        data = await _invidious_get(f"/api/v1/videos/{video_id}", {"fields": "title,videoId"})
        title = data.get("title", "Unknown") if data else "Unknown"
        return video_id, title

    results = await _invidious_get("/api/v1/search", {"q": query, "type": "video", "fields": "videoId,title"})
    if results and isinstance(results, list):
        first = results[0]
        return first["videoId"], first.get("title", "Unknown")
    return None


async def get_stream_url(video_id: str) -> str | None:
    data = await _invidious_get(
        f"/api/v1/videos/{video_id}",
        {"fields": "adaptiveFormats,formatStreams"}
    )
    if not data:
        return None

    best_url, best_bitrate = None, 0
    for fmt in data.get("adaptiveFormats", []):
        if fmt.get("type", "").startswith("audio/"):
            bitrate = int(fmt.get("bitrate", 0))
            if bitrate > best_bitrate:
                best_bitrate = bitrate
                best_url = fmt.get("url")

    if best_url:
        return best_url

    for fmt in data.get("formatStreams", []):
        if fmt.get("url"):
            return fmt["url"]

    return None


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _play_next(self, guild_id: int):
        player = get_player(guild_id)
        if not player.queue:
            player.current = None
            return

        vc = self._get_voice_client(guild_id)
        if not vc:
            player.current = None
            return

        song = player.queue.popleft()
        player.current = song
        source = discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTIONS)

        def after_play(error):
            if error:
                print(f"[Music ERROR] {error}")
            asyncio.run_coroutine_threadsafe(self._play_next(guild_id), self.bot.loop)

        vc.play(source, after=after_play)

    def _get_voice_client(self, guild_id: int) -> discord.VoiceClient | None:
        for vc in self.bot.voice_clients:
            if vc.guild.id == guild_id:
                return vc
        return None

    async def _disconnect(self, guild_id: int):
        player = get_player(guild_id)
        player.queue.clear()
        player.current = None
        vc = self._get_voice_client(guild_id)
        if vc:
            await vc.disconnect()
        player.voice_client = None

    @app_commands.command(name="play", description="Play a song from YouTube")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel first, peasant.")
            return

        player = get_player(interaction.guild_id)
        if not player.voice_client or not player.voice_client.is_connected():
            player.voice_client = await interaction.user.voice.channel.connect()
        elif player.voice_client.channel != interaction.user.voice.channel:
            await player.voice_client.move_to(interaction.user.voice.channel)

        try:
            result = await asyncio.wait_for(resolve_query(query), timeout=15)
        except asyncio.TimeoutError:
            await interaction.followup.send("*Chii-sama got tired of waiting.* Search took too long — try again.")
            return

        if not result:
            await interaction.followup.send("*Chii-sama couldn't find that.* Try a different search or URL.")
            return

        video_id, title = result

        try:
            stream_url = await asyncio.wait_for(get_stream_url(video_id), timeout=15)
        except asyncio.TimeoutError:
            await interaction.followup.send("*Chii-sama got tired of waiting.* Stream fetch timed out — try again.")
            return

        if not stream_url:
            await interaction.followup.send("*Chii-sama couldn't get the stream.* Try a different song.")
            return

        song = Song(url=stream_url, title=title, video_id=video_id, requester=interaction.user.display_name)
        player.queue.append(song)

        vc = self._get_voice_client(interaction.guild_id)
        if vc and not vc.is_playing() and not vc.is_paused():
            await self._play_next(interaction.guild_id)
            await interaction.followup.send(f"Now playing: **{song.title}**\nRequested by: {song.requester}")
        else:
            await interaction.followup.send(f"Added to queue (#{len(player.queue)}): **{song.title}**")

    @app_commands.command(name="leave", description="Chii-sama leaves the voice channel")
    async def leave(self, interaction: discord.Interaction):
        if not self._get_voice_client(interaction.guild_id):
            await interaction.response.send_message("I'm not even in a voice channel.")
            return
        await self._disconnect(interaction.guild_id)
        await interaction.response.send_message("*Chii-sama has left. You're welcome.*")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = self._get_voice_client(interaction.guild_id)
        if not vc or not vc.is_playing():
            await interaction.response.send_message("Nothing is playing right now.")
            return
        vc.stop()
        await interaction.response.send_message("*Chii-sama skips this inferior track.*")

    @app_commands.command(name="stop", description="Stop music and leave the voice channel")
    async def stop(self, interaction: discord.Interaction):
        await self._disconnect(interaction.guild_id)
        await interaction.response.send_message("*Chii-sama has left the stage. You're welcome.*")

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        vc = self._get_voice_client(interaction.guild_id)
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("*Chii-sama pauses for dramatic effect.*")
        else:
            await interaction.response.send_message("Nothing is playing.")

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        vc = self._get_voice_client(interaction.guild_id)
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("*The performance continues!*")
        else:
            await interaction.response.send_message("Nothing is paused.")

    @app_commands.command(name="queue", description="Show the current music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        player = get_player(interaction.guild_id)
        if not player.current and not player.queue:
            await interaction.response.send_message("The queue is empty. Request something worthy of Chii-sama!")
            return

        embed = discord.Embed(title="Chii-sama's Playlist", color=0xFFB7C5)
        if player.current:
            embed.add_field(
                name="Now Playing",
                value=f"**[{player.current.title}]({player.current.webpage_url})**\nRequested by {player.current.requester}",
                inline=False,
            )
        if player.queue:
            lines = [f"{i+1}. **{s.title}** — {s.requester}" for i, s in enumerate(player.queue)]
            embed.add_field(name="Up Next", value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show what's currently playing")
    async def nowplaying(self, interaction: discord.Interaction):
        player = get_player(interaction.guild_id)
        if not player.current:
            await interaction.response.send_message("Nothing is playing right now.")
            return
        embed = discord.Embed(title="Now Playing", color=0xFFB7C5)
        embed.add_field(
            name=player.current.title,
            value=f"[Open link]({player.current.webpage_url}) | Requested by {player.current.requester}",
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
