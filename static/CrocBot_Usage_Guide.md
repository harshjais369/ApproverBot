# Crocodile Game Bot Docs & Usage Guide

## 1. Project Overview
**Crocodile Game BOT** (@CrocodileGameEnn_bot) is the most advanced Telegram bot enabling an AI-powered multiplayer word-guessing games, also a built-in chatbot.
*   **Official Updates:** [t.me/CrocodileGames](https://t.me/CrocodileGames)
*   **Official Support/Game Group:** @CrocodileGamesGroup
*   **Creator & Owner:** Exception (@exceptionl)

## 2. Game Types
Crocodile Game Bot offers two exciting word games for group chats:
1.  **Word Guess** — One player (leader) gets a secret word from bot, others guess it from hints given by leader.
    *   Players take turns describing and guessing secret words, earning gold coins for correct guesses and successful leadership.
    *   **Winning reward:** gold coin.
    *   **Gold coin earned per round =** 1 for correct guess + 2 for successfully leading next round. *[More details in Economy (4th) section]*
2.  **Wordle** — Players guess the hidden 5-letter word with colored-letter clues within 30 max attempts.
    *   Green - Letter is correct and in correct position.
    *   Yellow - Letter is correct but in wrong position.
    *   Red - Letter is incorrect.
    *   **Winning reward:** diamond.
    *   **Diamond earned per round =** 31 - number of guesses taken to find correct one.
- **Game Flow:** Player who correctly guess the word before other, wins that round with reward.

## 3. Game Mechanics (Word Guess)
### Roles
*   **Leader:** Selected randomly or via Auto-Lead. Gets a **secret word** via bot (or can choose a custom one via "Write Word" button). Must describe it to others using text/media/voice without explicitly naming the word or its root forms.
*   **Participants:** Read hints and type guesses in the public chat.

### Gameplay Flow
1.  **Start:** `/game` initiates a round.
2.  **Describing:** Leader provides hints (definitions, synonyms, scenarios).
3.  **Guessing:** Participants type words.
4.  **Win:** First exact match wins. The winner typically becomes the next leader.
5.  **Timeout:** Game auto-stops if the leader does not view/know the word within 1 minute, or if doesn't provide hints within 5 minutes.

## 4. Rules & Economy (Word Guess)
*Currency is virtual and holds no real-world value. 💵 is represented as gold coin.*

| Action | Reward | Condition |
| :--- | :--- | :--- |
| **Correct Guess** | **+1 💵** | First player to type the secret word. |
| **Perfect Play** | **+3 💵** | Guess correctly (+1) AND successfully lead the immediate next round (+2). |
| **Word Leak** | **-1 💵** | Leader reveals the secret word in chat. |
| **Premature Guess** | **-1 💵** | Participant guesses correctly *before* the leader sends any hints (anti-cheat measure). |
| **Cheating** | **-1 💵** | Using whisper bots, external cheats, or unfair means. |

## 5. Command Reference
*   `/game` - Start a new game round (Word Guess or Wordle).
*   `/stop` - Stop active game (Leader/Admin only).
*   `/hint` (or `/who`, `/question`) - Show hints provided so far or request hint from AI (if applicable).
*   `/mystats` - View own game statistics and valid currency (Word Guess or Wordle).
*   `/stats` - Reply to other's message to view their stats (Word Guess or Wordle).
*   `/ranking` - Top 25 players in the current chat (Word Guess or Wordle).
*   `/globalranking` - Top 25 players across all chats (Word Guess or Wordle).
*   `/chatranking` - Top 10 groups by total earned amounts (Word Guess or Wordle).
*   `/addword <word>` - Submit a new word to the dictionary (to be approved by bot mods).
*   `/wordset` - View/change word set in current chat (Admin only).
*   `/settings` - Configure group/personal preferences.
*   `/rules` - Display game rules (Word Guess & Wordle).

## 6. AI Chatbot (Croco 2.0)
The bot also functions as a multimodal AI assistant & casual human-like chatbot supporting inputs in 15+ languages.
*   **Trigger:** Tag `@croco` or reply to the bot in the group.
*   **Capabilities:** General queries, image analysis, voice notes, and casual/fun talks.
*   **Availability:** In **Official Support Group** only.

## 7. AI & Safety Systems (Compliance)
The bot utilizes AI & smart algorithms to monitor gameplay fairness and content safety by itself automatically.

### Anti-Cheat
*   **Scope:** All chats globally.
*   **Detection:** Whisper bots, self-userbots, and collaborative cheating patterns.
*   **Action:** Immediate point deduction and potential user/group blocks.

### Anti-Spam Measures
*  **Scope:** All chats globally.
*  **Detection:** Sending multiple commands/requests to the bot in a short period.
*   **Action:** Rate limits are triggered, or immediate user/group blocks in extreme scenarios.

### Abuse Content Protection Policy
*   **Scope:** Strictly & exclusively enforced in the **Official Support Group** only; penalties apply globally.
*   **Prohibited Content:** Hate speech, sexual content (text/media), double meanings, illegal advertising, privacy breaches, and harassment.
*   **AI Decoding:** The bot analyzes standard text and **emoji combinations** for hidden meanings in leader's hints.
    *   *Example:* Identifying "🍑 + logic gate + ☀️" as an attempt to obscure inappropriate words (e.g., ass-er-tion).
*   **Enforcement:**
    1.  **Detection:** AI flags inappropriate content contextually.
    2.  **Action:** Immediate global ban from bot services and in extreme cases results removal from support group too.
    3.  **Appeals:** User must contact @admin with detailed justification. Multiple appeals (i.e. spam) in short intervals may cause a ban from group.

## 8. Troubleshooting
For issues not resolving via `/help` or `/rules`:
1.  Check the Official Channel for maintenance alerts.
2.  Contact admins in @CrocodileGamesGroup with specific screenshots/logs.
