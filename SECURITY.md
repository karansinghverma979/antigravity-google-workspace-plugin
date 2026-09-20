# Security Policy

## Supported Versions
Only the latest release receives active security patches.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0.0 | :x:                |

## Security Directives & Token Safety
- **OAuth Token Quarantine**: OAuth 2.0 credentials (`credentials.json`) and active tokens (`token.json`) are strictly git-ignored and must never be committed to source control.
- **Dynamic Path Expansion**: Token paths resolve dynamically via `GOOGLE_WORKSPACE_TOKEN_PATH` or local quarantine directories without hardcoded user profile paths.
- **Dispatch Firewall**: Outbound communications (`gmail_send_message`) and destructive actions (`gdrive_trash_file`, `gcal_delete_event`, `gtasks_delete_task`) require explicit confirmation protocols in companion agent skills.
- **Least-Privilege Scopes**: The plugin requests only necessary Google Workspace API scopes.

## Reporting a Vulnerability
**Please do not report security vulnerabilities through public GitHub issues.**

To report a vulnerability:
1. Use GitHub's private vulnerability reporting feature on the repository:
   `https://github.com/karansinghverma979/antigravity-google-workspace-plugin/security/advisories/new`
2. Maintainers will acknowledge within 48 hours and coordinate a public release upon resolution.
