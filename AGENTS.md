# AGENTS.md

## Purpose
This repository contains **Approver Bot**, a Python 3.12+ Telegram moderation bot with a Flask web app for join verification and browser-fingerprint based multi-account detection.

## Tech Stack
- Python 3.12+
- `pyTelegramBotAPI`
- Flask
- SQLite
- Docker / Docker Compose (production stack with nginx + certbot)

## Key Entry Points
- `/bot.py` — main bot + Flask routes
- `/config.py` — environment configuration
- `/database.py` — SQLite data access
- `/fingerprint.py` — fingerprint matching logic
- `/validation.py` — Telegram `initData` validation
- `/templates/verify.html` — Mini Web App verification page

## Local Development
1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy environment template:
   - `cp .env.example .env`
4. Update `.env` values.
5. Run locally:
   - `python bot.py`

## Validation Guidance
This repository does not currently define automated lint/test commands (no configured `pytest`, `ruff`, `flake8`, or `mypy` setup in-repo). For changes, at minimum:
- verify the app starts with `python bot.py` (with valid env values),
- and validate changed flows manually.

## Coding Conventions
Follow `CONTRIBUTING.md`:
- Follow PEP 8.
- Use type hints on function signatures.
- Add docstrings for public functions.
- Keep functions focused and reasonably small.
- Use clear variable names.
- Log important operations.

## Security and Secrets
- Never commit real bot tokens, chat IDs, SSH keys, or `.env` secrets.
- Keep `.env` values local only.
- Preserve verification security checks (`initData` HMAC validation) and join-flow protections.

## Deployment Notes
- CI/CD deploy workflow is defined at:
  - `/.github/workflows/deploy.yml`
- Production runtime uses Docker Compose and nginx configuration under:
  - `/docker-compose.yml`
  - `/nginx/`
