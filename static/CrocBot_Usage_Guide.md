# Crocodile Game Bot Docs & Usage Guide

## 1. Project Overview
**Crocodile Game BOT** (@CrocodileGameEnn_bot) is the most advanced Telegram bot enabling an AI-powered multiplayer word-guessing game, also built-in chatbot. Players take turns describing and guessing secret words, earning virtual currency (CrocCash 💵) for correct guesses and successful leadership.
*   **Official Updates:** [t.me/CrocodileGames](https://t.me/CrocodileGames)
*   **Official Support/Game Group:** @CrocodileGamesGroup
*   **Creator & Owner:** Exception (@exceptionl)

## 2. Game Mechanics
### Roles
*   **Leader:** Selected randomly or via Auto-Lead. Receives a **secret word** (or can choose a custom one via "Write Word" button). Must describe it to others using text/media/voice without explicitly naming the word or its root forms.
*   **Participants:** Read hints and type guesses in the public chat.

### Gameplay Flow
1.  **Start:** `/game` initiates a round.
2.  **Describing:** Leader provides hints (definitions, synonyms, scenarios).
3.  **Guessing:** Participants type words.
4.  **Win:** First exact match wins. The winner typically becomes the next leader.
5.  **Timeout:** Game auto-stops if the leader does not view/know the word within 1 minute, or if doesn't provide hints within 5 minutes.

## 3. Rules & Economy (CrocCash 💵)
*Currency is virtual and holds no real-world value.*

| Action | Reward | Condition |
| :--- | :--- | :--- |
| **Correct Guess** | **+1 💵** | First player to type the secret word. |
| **Perfect Play** | **+3 💵** | Guess correctly (+1) AND successfully lead the immediate next round (+2). |
| **Word Leak** | **-1 💵** | Leader reveals the secret word in chat. |
| **Premature Guess** | **-1 💵** | Participant guesses correctly *before* the leader sends any hints (anti-cheat measure). |
| **Cheating** | **-1 💵** | Using whisper bots, external cheats, or unfair means. |

## 4. Command Reference
*   `/game` - Start a new game / Join queue.
*   `/stop` - Stop active game (Leader/Admin only).
*   `/hint` (or `/who`, `/question`) - Show hints provided so far or request hint from AI (if applicable).
*   `/mystats` - View own game statistics and valid currency.
*   `/stats` - Reply to other's message to view their stats.
*   `/ranking` - Top 25 players in the current chat.
*   `/globalranking` - Top 25 players across all chats.
*   `/chatranking` - Top 10 groups by total CrocCash.
*   `/addword <word>` - Submit a new word to the dictionary (to be approved by bot mods).
*   `/wordset` - View/change word set in current chat (Admin only).
*   `/settings` - Configure user/group preferences (PM only).
*   `/rules` - Display game rules.

## 5. AI Chatbot (Croco 2.0)
The bot also functions as a multimodal AI assistant & casual human-like chatbot supporting inputs in 15+ languages.
*   **Trigger:** Tag `@croco` or reply to the bot in the group.
*   **Capabilities:** General queries, image analysis, voice notes, and casual/fun talks.
*   **Availability:** In **Official Support Group** only.

## 6. AI & Safety Systems (Compliance)
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

## 7. Troubleshooting
For issues not resolving via `/help` or `/rules`:
1.  Check the Official Channel for maintenance alerts.
2.  Contact admins in @CrocodileGamesGroup with specific screenshots/logs.
