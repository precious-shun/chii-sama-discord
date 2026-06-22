# Chii-sama Discord Bot

A Discord bot roleplaying as **Chitose Karasuma** from *Girlish Number*, powered by Google Gemini AI. Built with Python, discord.py, and SQLite.

---

## Commands

### General Use

| Command | Description | Parameters |
|---|---|---|
| `/ask` | Ask Chii-sama a question via Gemini | `question` |
| `/roast` | Have Chii-sama roast a server member | `target` (mention) |
| `/8ball` | Ask the magic 8-ball | `question` |
| `/pick` | Pick one option at random from a list | `options` (comma-separated) |
| `/daily` | Claim 100 coins once per day | — |
| `/coins` | Check your coin balance | — |
| `/leaderboard` | Show the top 10 coin holders | — |
| `/rps` | Rock paper scissors vs Chii-sama — win 50 coins | `choice` |
| `/draw` | Generate an image from a prompt | `prompt` |
| `/urban` | Look up a term on Urban Dictionary (paginated) | `term` |
| `/cm` | Make Chii-sama send a message as herself *(DM/puppet ppl only)* | `message` |

**Passive triggers (no command needed):**
- Mentioning **Chii-sama**, **Chitose**, or **Karasuma** in a message triggers a reply
- @mentioning the bot triggers a reply
- Replying to one of Chii-sama's messages continues the conversation
- `?beyond <url or ID>` links a D&D Beyond character sheet to your account (shorthand alternative to `/linkcharacter`)

---

### D&D Use

#### Player Commands

| Command | Description | Parameters |
|---|---|---|
| `/linkcharacter` | Link your D&D Beyond character sheet for roll modifiers | `url` (URL or character ID) |
| `/dndskillissue` | Get Gemini-powered tactical advice based on your linked character sheet | `obstacle` |
| `/footnote` | Add a personal note to a main quest in the journal | `name` (quest), `footnote` |
| `/questjournal` | Show the party's current quest journal | — |

#### DM / Admin Commands *(DM or puppet ppl role required)*

| Command | Description | Parameters |
|---|---|---|
| `/setcampaign` | Set the active campaign name for this server | `name` |
| `/rollrequest` | Request up to 6 players to roll a skill check with interactive buttons | `check`, `player1–6`, `mode1–6`, `everyone`, `required` |
| `/sessionstart` | Start recording a session in the current channel | — |
| `/sessionend` | End the session and generate a structured summary | — |
| `/createquest` | Add a new main or side quest to the journal | `quest_type`, `name`, `objective`, `description` |
| `/updatequest` | Update quest status, description, or objectives | `quest_type`, `name`, `status`\*, `objective`\*, `description`\*, `add_objective`\* |
| `/deletequest` | Delete a quest from the journal | `quest_type`, `name` |

\* optional

**Passive triggers (D&D):**
- Saying **"quest journal"** in a channel with an active session generates a storyteller-style chronicle of the session so far plus up to 4 quest hook suggestions
- Adding a footnote announces `{character} scribbled something on #newbies-quest-journal` in the current channel

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
