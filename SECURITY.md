# Security Policy

## Privacy First

LifeVault is designed with privacy as a core principle. All data processing happens **locally on your machine** — we never transmit your personal data to external servers.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT open a public issue**
2. Email the maintainers at: [Create a private security advisory on GitHub]
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to address the issue.

## Security Best Practices

When using LifeVault:

### Data Storage
- All data is stored locally in SQLite databases
- Database files are **not encrypted by default** — use disk encryption (BitLocker, FileVault, LUKS) for additional protection
- Regularly back up your `~/.lifevault/` directory to secure locations

### Data Export
- Exported files (JSON, CSV) contain **unencrypted personal data**
- Use `mask_sensitive=true` when exporting data for sharing; this masks phone numbers, ID cards, emails, local file paths, and optional custom terms
- Export masking does **not** modify the original local database
- Store exports securely and delete them when no longer needed
- Be cautious when sharing exports — they may contain sensitive information
- See [Privacy Masking Design](docs/PRIVACY_MASKING.md) for the masking threat model and accepted risks

### Network Security
- LifeVault's backend API runs on `localhost:8000` by default
- **Do NOT expose the API to the public internet** without proper authentication
- If you must expose it, use a reverse proxy with TLS and authentication

### Third-Party Integrations
- Future versions may include LLM-based features (v0.2.0+)
- When enabled, chat messages may be sent to LLM APIs (OpenAI, Anthropic, etc.)
- Review the privacy policies of third-party services before enabling integrations

## Known Security Considerations

### Database File Access
- Anyone with access to your `.db` files can read your messages
- Use OS-level file permissions to restrict access
- Consider full-disk encryption for sensitive data

### Import Data Sources
- Be cautious when importing data from untrusted sources
- Review imported data before processing
- The import feature does basic validation but cannot guarantee data integrity

### Browser Security
- The frontend UI runs in your browser on `localhost:3000`
- Modern browsers isolate localhost from external origins
- Keep your browser updated to the latest version

## Security Roadmap

Planned security enhancements:

### v0.2.0
- [x] Privacy masking for exported data (phone numbers, IDs, emails, file paths, custom terms)
- [ ] Automatic name/address detection
- [ ] Data anonymization features
- [ ] Export encryption options

### v0.3.0
- [ ] Optional database encryption
- [ ] Authentication for API access
- [ ] Audit logging

## Acknowledgments

We follow security best practices from:
- OWASP Top 10
- CWE/SANS Top 25
- Python security guidelines
- FastAPI security recommendations

## Contact

For security concerns, please use GitHub's private security advisory feature or contact the maintainers directly.
