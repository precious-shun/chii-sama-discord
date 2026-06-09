import asyncio
import os
from collections import deque

import discord
import yt_dlp

os.environ['PATH'] = '/home/chiisama/.deno/bin:' + os.environ.get('PATH', '')
from discord import app_commands
from discord.ext import commands

YTDL_OPTIONS = {
    'format': 'bestaudio/best[height<=480]/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'cookiefile': '/opt/chii-sama/cookies.txt',
    'extractor_args': {
        'youtube': {
            'js_runtimes': ['deno:/home/chiisama/.deno/bin/deno'],
        }
    },
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}


class Song:
    def __init__(self, url: str, title: str, webpage_url: str, requester: str):
        self.url = url
        self.title = title
        self.webpage_url = webpage_url
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


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _play_next(self, guild_id: int):
        player = get_player(guild_id)
        if not player.queue or not player.voice_client:
            player.current = None
            return

        song = player.queue.popleft()
        player.current = song
        source = discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTIONS)

        def after_play(error):
            if error:
                print(f"[Music ERROR] {error}")
            asyncio.run_coroutine_threadsafe(self._play_next(guild_id), self.bot.loop)

        player.voice_client.play(source, after=after_play)

    async def _ensure_voice(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.voice:
            await interaction.response.send_message(
                "You need to be in a voice channel first, peasant."
            )
            return False
        player = get_player(interaction.guild_id)
        if not player.voice_client or not player.voice_client.is_connected():
            player.voice_client = await interaction.user.voice.channel.connect()
        elif player.voice_client.channel != interaction.user.voice.channel:
            await player.voice_client.move_to(interaction.user.voice.channel)
        return True

    @app_commands.command(name="play", description="Play a song from YouTube, YouTube Music, or SoundCloud")
    @app_commands.describe(query="Song name or paste a URL")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel first, peasant.")
            return

        player = get_player(interaction.guild_id)
        print(f"[Music] Connecting to voice for guild {interaction.guild_id}...")
        if not player.voice_client or not player.voice_client.is_connected():
            player.voice_client = await interaction.user.voice.channel.connect()
        elif player.voice_client.channel != interaction.user.voice.channel:
            await player.voice_client.move_to(interaction.user.voice.channel)
        print(f"[Music] Voice connected. Fetching: {query!r}")

        loop = asyncio.get_running_loop()
        try:
            ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False)),
                timeout=30,
            )
            if 'entries' in data:
                data = data['entries'][0]
            print(f"[Music] Fetched: {data.get('title')!r}")
        except asyncio.TimeoutError:
            print(f"[Music] yt_dlp timed out for query: {query!r}")
            await interaction.followup.send("*Chii-sama got tired of waiting.* YouTube took too long — try again.")
            return
        except Exception as e:
            print(f"[Music ERROR] {type(e).__name__}: {e}")
            await interaction.followup.send(
                "*Chii-sama couldn't find that.* Try a different search or URL."
            )
            return

        song = Song(
            url=data['url'],
            title=data.get('title', 'Unknown'),
            webpage_url=data.get('webpage_url', query),
            requester=interaction.user.display_name,
        )

        player = get_player(interaction.guild_id)
        player.queue.append(song)

        if not player.voice_client.is_playing() and not player.voice_client.is_paused():
            await self._play_next(interaction.guild_id)
            await interaction.followup.send(
                f"Now playing: **{song.title}**\nRequested by: {song.requester}"
            )
        else:
            await interaction.followup.send(
                f"Added to queue (#{len(player.queue)}): **{song.title}**"
            )

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        player = get_player(interaction.guild_id)
        if not player.voice_client or not player.voice_client.is_playing():
            await interaction.response.send_message("Nothing is playing right now.")
            return
        player.voice_client.stop()
        await interaction.response.send_message("*Chii-sama skips this inferior track.*")

    @app_commands.command(name="stop", description="Stop music and leave the voice channel")
    async def stop(self, interaction: discord.Interaction):
        player = get_player(interaction.guild_id)
        if player.voice_client:
            player.queue.clear()
            player.current = None
            await player.voice_client.disconnect()
            player.voice_client = None
        await interaction.response.send_message("*Chii-sama has left the stage. You're welcome.*")

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        player = get_player(interaction.guild_id)
        if player.voice_client and player.voice_client.is_playing():
            player.voice_client.pause()
            await interaction.response.send_message("*Chii-sama pauses for dramatic effect.*")
        else:
            await interaction.response.send_message("Nothing is playing.")

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        player = get_player(interaction.guild_id)
        if player.voice_client and player.voice_client.is_paused():
            player.voice_client.resume()
            await interaction.response.send_message("*The performance continues!*")
        else:
            await interaction.response.send_message("Nothing is paused.")

    @app_commands.command(name="queue", description="Show the current music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        player = get_player(interaction.guild_id)
        if not player.current and not player.queue:
            await interaction.response.send_message(
                "The queue is empty. Request something worthy of Chii-sama!"
            )
            return

        embed = discord.Embed(title="Chii-sama's Playlist", color=0xFFB7C5)
        if player.current:
            embed.add_field(
                name="Now Playing",
                value=f"**[{player.current.title}]({player.current.webpage_url})**\nRequested by {player.current.requester}",
                inline=False,
            )
        if player.queue:
            lines = [
                f"{i+1}. **{s.title}** — {s.requester}"
                for i, s in enumerate(player.queue)
            ]
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
