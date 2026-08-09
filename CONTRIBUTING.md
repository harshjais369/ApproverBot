# Contributing to ApproverBot

Thank you for your interest in contributing! Please read these guidelines before submitting changes.

## ⚠️ Important: Proprietary Software

This project is **proprietary software** (All Rights Reserved). By submitting a contribution, you agree that:

1. Your contribution becomes the property of Crocodile Games
2. You have the right to submit the contribution
3. Your contribution does not contain code from incompatibly licensed projects

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/harshjais369/ApproverBot/issues) to avoid duplicates
2. Use the **Bug Report** issue template
3. Include steps to reproduce, expected behavior, and actual behavior
4. For security vulnerabilities, see [SECURITY.md](SECURITY.md) instead

### Suggesting Features

1. Open an issue using the **Feature Request** template
2. Describe the problem your feature solves
3. Provide examples or mockups if possible

### Submitting Code Changes

1. **Fork** the repository
2. Create a feature branch from `main`: `git checkout -b feature/your-feature`
3. Make your changes following the code style guidelines below
4. Test your changes locally
5. Commit with a clear, descriptive message
6. Push and open a **Pull Request**

## Code Style Guidelines

- **Python**: Follow PEP 8 conventions
- Use type hints for function signatures
- Write docstrings for all public functions
- Keep functions focused and under 50 lines where possible
- Use meaningful variable names (no single-letter names except loop counters)
- Log important operations using the `logger` module

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/ApproverBot.git
cd ApproverBot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate    # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your test bot token and settings
```

## Pull Request Checklist

- [ ] Code follows the style guidelines
- [ ] Self-reviewed the changes
- [ ] Added/updated comments and docstrings where needed
- [ ] No secrets, tokens, or personal data in the commit
- [ ] Tested locally with a test bot
- [ ] No breaking changes to the database schema (or migration included)

## Questions?

Reach out in the [Crocodile Games Group](https://t.me/CrocodileGamesGroup) or contact [@exceptionl](https://t.me/exceptionl).
