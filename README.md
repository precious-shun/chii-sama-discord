# Chii-sama Discord Bot

A Discord bot roleplaying as **Chitose Karasuma** from *Girlish Number*, powered by Google Gemini AI. Built with Python, discord.py, and SQLite.

---

## Changelog

### v0.8.0 — Urban Dictionary (2026-06-21)
- Add `/urban` command using the official Urban Dictionary API
- Results sorted by upvotes
- Paginate through definitions with ◀ Prev / Next ▶ buttons (wraps at end)
- Full embed: definition, example, vote counts, author, date written

---

### v0.7.0 — Roll Request Improvements (2026-06-12)
- `/rollrequest` now supports `everyone=True` to tag all campaign players at once
- Added `required` flag — shows "MAY roll" when set to False
- Buttons auto-populate for all linked campaign characters
- Fixed button rendering when using member cache vs. fetched members
- Fixed everyone/required choice ordering in Discord UI

---

### v0.6.1 — Music (experimental, non-functional) (2026-06-09 – 2026-06-12)
- Attempted `/play`, `/stop`, `/leave` music commands via yt-dlp, Invidious, Lavalink/wavelink, and InnerTube
- YouTube bot detection blocked every approach tried
- Music commands exist in code but are not reliably usable

---

### v0.6.0 — D&D Tactical Advisor + Homebrew Checks (2026-06-06 – 2026-06-08)
- Add `/dndskillissue` — Gemini-powered tactical advice based on linked D&D Beyond character sheet
- Pulls full character data: stats, skills, spells, inventory, feats, class features
- Automatically fetches party member sheets when mentioned in the situation description
- Splits long responses across multiple embeds
- Add **Hamingja** homebrew check (1d6, no modifiers)
- Add **Martial** and **Spiritual** composite checks (sum of multiple stat modifiers)
- `/setcampaign` command to name the active D&D campaign

---

### v0.5.0 — D&D Roll System (2026-06-05 – 2026-06-06)
- Add `/rollrequest` — DM requests skill checks from specific players with interactive buttons
- Supports up to 6 players, each with Normal / Advantage / Disadvantage mode
- Buttons are player-locked (only the tagged player can click their own button)
- Roll results posted as embeds with character portrait thumbnail
- Fuzzy autocomplete for check names (skills, abilities, saving throws, abbreviations)
- D&D Beyond character linking via `/linkcharacter` or `?beyond <url>`
- Roll modifiers automatically calculated from linked character sheet (proficiency, expertise, half-prof)
- Character name used as button label when a sheet is linked
- Natural 1 / natural max displayed in bold; nat 20 triggers 勝ったな！ガハハ！
- `/cm` command for DM to speak as the bot (DM/puppet ppl role only)

---

### v0.4.0 — Image Generation (2026-06-04 – 2026-06-05)
- Add `/draw` command — generates images from a text prompt
- Iterated through Imagen 4, Pollinations.ai, Stable Horde, Hugging Face FLUX, then settled on **Cloudflare Workers AI (FLUX.1-Schnell)**
- Prompt automatically boosted with quality tags
- Response includes a randomized Chitose flavor line

---

### v0.3.0 — News Awareness (2026-05-29)
- Chitose can now fetch and relay current headlines
- Staged behavior: deflects non-Japan news, actually checks for Japan news, mangles foreign news on third ask
- Headlines fetched via Google News RSS (Japan, Indonesia, world)
- Region auto-detected from conversation context

---

### v0.2.0 — Personality & Core Features (2026-05-25 – 2026-05-26)
- Major Chitose system prompt rewrite — deeper character layers, dark humor, self-awareness, relationship tiering, calculated cuteness, core motivation
- Added 勝ったな！ガハハ！ as Chitose's victory catchphrase
- Gemini key rotation with fallback to gemini-3.5-flash when all keys exhausted
- Follow-up detection — bot responds to messages in context even without a direct mention
- Add `/ask`, `/roast`, `/8ball` commands
- Add `/pick` — random choice from a comma-separated list
- Add `/daily`, `/coins`, `/leaderboard`, `/rps` — coin economy

---

### v0.1.0 — Initial Bot (2026-05-25)
- Discord bot as Chitose Karasuma, responding to name triggers and @mentions
- Google Gemini AI backend (gemini-2.5-flash)
- SQLite conversation history per channel
- Reply-chain awareness (detects when replying to the bot vs. others)
- `[direct]` / `[mention]` / `[insult]` response tagging system
