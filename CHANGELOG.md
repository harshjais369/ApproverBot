# Changelog

All notable changes to ApproverBot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Initial public repository setup
- Telegram Mini Web App verification flow
- Browser fingerprint collection (15+ signals)
- Multi-account detection via weighted similarity scoring
- Fast-path detection for device_id and IP address matches
- Transitive cluster discovery via recursive CTE queries
- Bot API 10.1 support (`sendChatJoinRequestWebApp`, `answerChatJoinRequestQuery`)
- Admin notification system with inline action buttons
- Docker Compose production stack (bot + nginx + certbot)
- GitHub Actions CI/CD pipeline (push-to-deploy)
- SQLite database with WAL mode
- IP geolocation enrichment via ip-api.com
- Automated database backup script
- Comprehensive README documentation
- Security policy (SECURITY.md)
- Contributing guidelines (CONTRIBUTING.md)
- Code of Conduct
- `/fingerprint` (or `/fp`) command for viewing detailed user fingerprint data
- `restore-db.sh` script for safely restoring database backups into the Docker container
- `AGENTS.md` documentation for AI assistant guidance
- Dependabot configuration for automated dependency updates
- `FUNDING.yml` for project sponsorship
- Explicit permission blocks in GitHub Actions workflows

### Changed
- Enhanced the `/links` (and `/connections`) command output
- Updated deploy script to automatically back up the database before re-deploying
- Updated `README.md` to document new commands, restore scripts, updated schemas, and accurate CI/CD workflow steps
- Bumped Python base image from `3.12-slim` to `3.14-slim`
- Updated project dependencies (`pyTelegramBotAPI`, `Flask`, `python-dotenv`, `appleboy/ssh-action`)
- Minor updates to group terms and conditions

### Removed
- Removed TeleBot Bot API 10.1 monkey patch (now supported natively)
