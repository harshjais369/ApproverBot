# Security Policy

## Supported Versions

| Version | Supported |
|:--------|:---------:|
| Latest (main branch) | ✅ |
| Older commits | ❌ |

## Reporting a Vulnerability

If you discover a security vulnerability in ApproverBot, **please do NOT open a public GitHub issue.**

Instead, report it privately through one of these channels:

1. **Telegram:** Contact [@exceptionl](https://t.me/exceptionl) directly
2. **GitHub Security Advisories:** Use the [private vulnerability reporting](https://github.com/harshjais369/ApproverBot/security/advisories/new) feature

### What to Include

- A clear description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Suggested fix (if you have one)

### Response Timeline

| Action | Timeframe |
|:-------|:----------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 1 week |
| Fix deployed (critical) | Within 72 hours of confirmation |
| Fix deployed (non-critical) | Within 2 weeks of confirmation |

### Scope

The following areas are in scope for security reports:

- Authentication / authorization bypass
- Fingerprint data leakage or privacy violations
- Telegram `initData` validation bypass
- SQL injection or database manipulation
- Rate limiting bypass
- Unauthorized access to admin commands
- Information disclosure via API responses

### Out of Scope

- Denial of Service (DoS) attacks
- Social engineering attacks
- Issues in third-party dependencies (report upstream)
- Issues requiring physical access to the server

## Security Measures

For details on the security measures implemented in this project, see the
[Security Considerations](README.md#security-considerations) section of the README.
