import asyncio
import re
from collections import deque

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

# ── InnerTube endpoints ────────────────────────────────────────────────────────
_SEARCH_URL = "https://music.youtube.com/youtubei/v1/search?prettyPrint=false"
_PLAYER_URL = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
_YT_ID_RE   = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})')

# Clients with useSignatureTimestamp=False → return direct (non-ciphered) stream URLs.
# Exact versions from Metrolist's YouTubeClient.kt.
_PLAYER_CLIENTS = [
    {
        "name": "IOS",
        "ctx": {
            "clientName": "IOS",
            "clientVersion": "21.03.1",
            "osVersion": "18.2.22C152",
            "hl": "en", "gl": "US",
        },
        "userAgent": "com.google.ios.youtube/21.03.1 (iPhone16,2; U; CPU iOS 18_2 like Mac OS X;)",
        "embedUrl": None,
    },
    {
        "name": "ANDROID_VR",
        "ctx": {
            "clientName": "ANDROID_VR",
            "clientVersion": "1.61.48",
            "hl": "en", "gl": "US",
        },
        "userAgent": "com.google.android.apps.youtube.vr.oculus/1.61.48 (Linux; U; Android 12; en_US; Oculus Quest 3; Build/SQ3A.220605.009.A1; Cronet/132.0.6808.3)",
        "embedUrl": None,
    },
    {
        "name": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
        "ctx": {
            "clientName": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
            "clientVersion": "2.0",
            "hl": "en", "gl": "US",
        },
        "userAgent": "Mozilla/5.0 (PlayStation; PlayStation 4/12.02) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15",
        "embedUrl": "https://www.youtube.com/",
    },
]

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}


# ── InnerTube helpers ──────────────────────────────────────────────────────────

async def _search(query: str) -> tuple[str, str] | None:
    """Search YouTube Music via InnerTube. Returns (video_id, title) or None."""
    m = _YT_ID_RE.search(query)
    if m:
        return m.group(1), query

    body = {
        "context": {
            "client": {
                "clientName": "WEB_REMIX",
                "clientVersion": "1.20260213.01.00",
                "hl": "en", "gl": "US",
            }
        },
        "query": query,
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
        "Origin": "https://music.youtube.com",
        "Referer": "https://music.youtube.com/",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                _SEARCH_URL, json=body, headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    print(f"[Music] Search HTTP {resp.status}")
                    return None
                data = await resp.json()
    except Exception as e:
        print(f"[Music] Search error: {e}")
        return None

    video_id = _dig_video_id(data)
    if not video_id:
        return None
    title = _dig_title(data, video_id) or query
    return video_id, title


def _dig_video_id(node, depth=0):
    if depth > 20:
        return None
    if isinstance(node, dict):
        vid = node.get("videoId")
        if isinstance(vid, str) and len(vid) == 11:
            return vid
        for v in node.values():
            r = _dig_video_id(v, depth + 1)
            if r:
                return r
    elif isinstance(node, list):
        for item in node:
            r = _dig_video_id(item, depth + 1)
            if r:
                return r
    return None


def _dig_title(node, video_id, depth=0):
    if depth > 20:
        return None
    if isinstance(node, dict):
        if node.get("videoId") == video_id:
            t = node.get("title")
            if isinstance(t, str):
                return t
            if isinstance(t, dict):
                runs = t.get("runs", [])
                if runs:
                    return "".join(r.get("text", "") for r in runs)
        for v in node.values():
            r = _dig_title(v, video_id, depth + 1)
            if r:
                return r
    elif isinstance(node, list):
        for item in node:
            r = _dig_title(item, video_id, depth + 1)
            if r:
                return r
    return None


async def _get_stream(video_id: str) -> tuple[str, str, list[str]] | None:
    """Try each client in order. Returns (stream_url, title, debug_lines) or None."""
    debug = []
    for client in _PLAYER_CLIENTS:
        result, reason = await _try_client(video_id, client)
        if result:
            debug.append(f"✅ {client['name']}: OK")
            return result[0], result[1], debug
        debug.append(f"❌ {client['name']}: {reason}")
    return None, None, debug


async def _try_client(video_id: str, client: dict) -> tuple[tuple | None, str]:
    """Returns ((url, title), '') on success or (None, reason) on failure."""
    body: dict = {
        "context": {"client": client["ctx"]},
        "videoId": video_id,
        "contentCheckOk": True,
        "racyCheckOk": True,
    }
    if client["embedUrl"]:
        body["context"]["thirdParty"] = {"embedUrl": client["embedUrl"]}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": client["userAgent"],
        "Origin": "https://www.youtube.com",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                _PLAYER_URL, json=body, headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None, f"HTTP {resp.status}"
                data = await resp.json()
    except Exception as e:
        print(f"[Music] {client['name']} request failed: {e}")
        return None, f"request error: {e}"

    status = data.get("playabilityStatus", {})
    if status.get("status") != "OK":
        reason = status.get("reason") or status.get("status") or "unknown"
        print(f"[Music] {client['name']}: not playable — {reason}")
        return None, f"not playable: {reason}"

    title = data.get("videoDetails", {}).get("title", video_id)
    formats = data.get("streamingData", {}).get("adaptiveFormats", [])

    audio = [
        f for f in formats
        if f.get("url") and f.get("mimeType", "").startswith("audio/")
    ]
    if not audio:
        total_formats = len(formats)
        print(f"[Music] {client['name']}: no direct audio URLs (may be ciphered), total formats={total_formats}")
        return None, f"no direct audio URLs (total formats: {total_formats})"

    def _score(f):
        mime = f.get("mimeType", "")
        return (2 if "opus" in mime else 1) * 1_000_000 + f.get("bitrate", 0)

    best = max(audio, key=_score)
    print(f"[Music] {client['name']}: got '{title}' — {best.get('mimeType')} {best.get('bitrate', 0)//1000}kbps")
    return (best["url"], title), ""


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

        result = await _search(query)
        if not result:
            await interaction.followup.send("*Chii-sama couldn't find that.* Try a different search.")
            return

        video_id, _ = result
        stream_url, title, debug_lines = await _get_stream(video_id)
        if not stream_url:
            debug_text = "\n".join(debug_lines) if debug_lines else "no clients tried"
            await interaction.followup.send(
                f"*Chii-sama couldn't get the stream.* `video_id={video_id}`\n```\n{debug_text}\n```"
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
