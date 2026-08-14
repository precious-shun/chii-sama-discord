import asyncio
import re
from collections import deque

import discord
from discord import app_commands
from discord.ext import commands

# ── yt-dlp fetching ──────────────────────────────────────────────────────────
# Uses yt-dlp + the bgutil-pot PO Token provider (see /home/chiisama/yt-dlp.conf)
# instead of hand-rolled InnerTube requests — yt-dlp's client fallback chain and
# PO Token support are actively maintained against YouTube's bot checks, which
# our old hardcoded client list eventually fell behind on ("Sign in to confirm
# you're not a bot"). See music.py.bak.* for the previous implementation.
_YTDLP_BIN  = "/opt/chii-sama/venv/bin/yt-dlp"
_YTDLP_CONF = "/home/chiisama/yt-dlp.conf"
_YT_ID_RE   = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})')

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}


# ── yt-dlp helpers ──────────────────────────────────────────────────────────

async def _run_ytdlp(*args: str, timeout: float = 25) -> tuple[int, str, str]:
    """Run yt-dlp with our config (plugin-dirs, client fallback list, js runtime).
    Returns (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        _YTDLP_BIN, "--config-location", _YTDLP_CONF, *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return -1, "", "yt-dlp timed out"
    return proc.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


async def _candidates(query: str) -> list[tuple[str, str]]:
    """Resolve a search query or direct URL/ID to (video_id, title) candidates.
    Multiple candidates let us fall through to a different upload (e.g. a lyric
    video or official audio) if the top hit is blocked with a bot check."""
    m = _YT_ID_RE.search(query)
    if m:
        return [(m.group(1), query)]

    code, out, err = await _run_ytdlp(
        "--flat-playlist", "--print", "%(id)s\t%(title)s", f"ytsearch3:{query}",
        timeout=15,
    )
    if code != 0 or not out.strip():
        reason = err.strip().splitlines()[-1] if err.strip() else f"exit code {code}"
        print(f"[Music] search failed: {reason}")
        return []

    candidates = []
    for line in out.strip().splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            candidates.append((parts[0], parts[1]))
    return candidates


async def _get_stream(video_id: str) -> tuple[str | None, str | None, list[str]]:
    """Resolve a direct playable audio URL for video_id via yt-dlp.
    Returns (stream_url, title, debug_lines); stream_url is None on failure."""
    code, out, err = await _run_ytdlp(
        "-f", "bestaudio/best", "--no-playlist",
        "--print", "%(title)s\t%(url)s",
        video_id,
    )
    if code != 0 or not out.strip():
        reason = err.strip().splitlines()[-1] if err.strip() else f"exit code {code}"
        print(f"[Music] {video_id}: {reason}")
        return None, None, [reason]

    line = out.strip().splitlines()[-1]
    try:
        title, url = line.split("\t", 1)
    except ValueError:
        return None, None, [f"unparsable yt-dlp output: {line!r}"]
    print(f"[Music] {video_id}: got '{title}'")
    return url, title, []


async def _search_and_resolve(query: str) -> tuple[str | None, str | None, str | None, list[str]]:
    """Search for query, then try each candidate until one resolves to a stream.
    Returns (video_id, stream_url, title, debug_lines)."""
    candidates = await _candidates(query)
    if not candidates:
        return None, None, None, ["no search results"]

    debug = []
    for video_id, title in candidates:
        url, resolved_title, reasons = await _get_stream(video_id)
        if url:
            debug.append(f"✅ {title}: OK")
            return video_id, url, resolved_title or title, debug
        debug.append(f"❌ {title}: {reasons[0] if reasons else 'unknown error'}")
    return None, None, None, debug


# ── Guild state ────────────────────────────────────────────────────────────────

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


_players: dict[int, GuildPlayer] = {}


def _get_player(guild_id: int) -> GuildPlayer:
    if guild_id not in _players:
        _players[guild_id] = GuildPlayer()
    return _players[guild_id]


# ── Cog ────────────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _vc(self, guild: discord.Guild) -> discord.VoiceClient | None:
        return guild.voice_client  # type: ignore

    async def _play_next(self, guild_id: int):
        player = _get_player(guild_id)
        if not player.queue:
            player.current = None
            return
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        vc = self._vc(guild)
        if not vc:
            return

        song = player.queue.popleft()
        player.current = song
        source = discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTIONS)

        def after(error):
            if error:
                print(f"[Music] Playback error: {error}")
            asyncio.run_coroutine_threadsafe(self._play_next(guild_id), self.bot.loop)

        vc.play(source, after=after)

    # --- WAVELINK APPROACH (public Lavalink nodes — disabled) ---
    # Hits YouTube Music rate limits after ~1 natural stream completion.
    #
    # @app_commands.command(name="play", description="Play a song from YouTube")
    # @app_commands.describe(query="Song name or YouTube URL")
    # async def play_wavelink(self, interaction, query):
    #     ... (see git history)
    # --- END WAVELINK APPROACH ---

    @app_commands.command(name="play", description="Play a song from YouTube")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel first, peasant.")
            return

        vc = self._vc(interaction.guild)
        if not vc:
            vc = await interaction.user.voice.channel.connect()
        elif vc.channel != interaction.user.voice.channel:
            await vc.move_to(interaction.user.voice.channel)

        video_id, stream_url, title, debug_lines = await _search_and_resolve(query)
        if not stream_url:
            debug_text = "\n".join(debug_lines) if debug_lines else "no candidates tried"
            await interaction.followup.send(
                f"*Chii-sama couldn't get the stream.*\n```\n{debug_text}\n```"
            )
            return
        player = _get_player(interaction.guild_id)
        song = Song(url=stream_url, title=title, video_id=video_id, requester=interaction.user.display_name)
        player.queue.append(song)

        if not vc.is_playing() and not vc.is_paused():
            await self._play_next(interaction.guild_id)
            await interaction.followup.send(f"*Chii-sama graces you with music.* Now playing: **{title}**")
        else:
            await interaction.followup.send(f"Added to queue (#{len(player.queue)}): **{title}**")

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        vc = self._vc(interaction.guild)
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("*Chii-sama pauses for dramatic effect.*")
        else:
            await interaction.response.send_message("Nothing is playing.")

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        vc = self._vc(interaction.guild)
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("*The performance continues!*")
        else:
            await interaction.response.send_message("Nothing is paused.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = self._vc(interaction.guild)
        if not vc or not vc.is_playing():
            await interaction.response.send_message("Nothing is playing right now.")
            return
        vc.stop()
        await interaction.response.send_message("*Chii-sama skips this inferior track.*")

    @app_commands.command(name="stop", description="Stop music and leave the voice channel")
    async def stop(self, interaction: discord.Interaction):
        player = _get_player(interaction.guild_id)
        player.queue.clear()
        player.current = None
        vc = self._vc(interaction.guild)
        if vc:
            await vc.disconnect()
        await interaction.response.send_message("*Chii-sama has left the stage. You're welcome.*")

    @app_commands.command(name="leave", description="Chii-sama leaves the voice channel")
    async def leave(self, interaction: discord.Interaction):
        vc = self._vc(interaction.guild)
        if not vc:
            await interaction.response.send_message("I'm not even in a voice channel.")
            return
        player = _get_player(interaction.guild_id)
        player.queue.clear()
        player.current = None
        await vc.disconnect()
        await interaction.response.send_message("*Chii-sama has left. You're welcome.*")

    @app_commands.command(name="queue", description="Show the current music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        player = _get_player(interaction.guild_id)
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
            embed.add_field(name="Up Next", value="\n".join(lines[:10]), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show what's currently playing")
    async def nowplaying(self, interaction: discord.Interaction):
        player = _get_player(interaction.guild_id)
        if not player.current:
            await interaction.response.send_message("Nothing is playing right now.")
            return
        t = player.current
        embed = discord.Embed(title="Now Playing", color=0xFFB7C5)
        embed.add_field(
            name=t.title,
            value=f"[Open link]({t.webpage_url}) | Requested by {t.requester}",
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
