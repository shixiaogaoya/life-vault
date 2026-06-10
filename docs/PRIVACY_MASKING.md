# Privacy Masking Design

**Last updated:** 2026-06-10

## Goal

Export masking and sharing anonymization reduce accidental exposure when users share LifeVault exports or reports. They are export-time protection layers: the original local SQLite database remains unchanged.

## Threat Model

Masking is designed to reduce exposure of common personal identifiers in exported JSON, CSV, Markdown, HTML, and report payloads:

- Chinese mobile phone numbers
- Chinese resident ID cards
- Email addresses
- Common local file paths
- Chinese names detected from message sender/chat fields
- Common Chinese address-like text fragments
- User-provided custom terms such as names, addresses, company names, or aliases

Sharing anonymization is designed for exports that need stronger redaction before sharing:

- Replace sender and chat names/IDs with stable per-export pseudonyms such as `Person 1` and `Chat 1`
- Remove location message content (`msg_type=48`) from exported payloads
- Replace location-like metadata fields such as `latitude`, `longitude`, `address`, and `poi` with `[LOCATION_REMOVED]`
- Sanitize common local file paths with `[PATH]`

## Security Boundary

- Masking applies only when `mask_sensitive=true` is passed to an export endpoint.
- Sharing anonymization applies only when `anonymize=true` is passed to an export endpoint.
- Masking is deterministic string replacement, not cryptographic anonymization.
- Sharing anonymization uses deterministic pseudonyms inside one export payload, but pseudonym numbering is not a durable identity system across separate exports.
- The local database, in-memory query results, and original imported records remain unmodified.
- Name/address detection is conservative and rule-based; custom terms are still recommended for names, aliases, and addresses that do not match the built-in patterns.
- Masked exports are still unencrypted files; users should store and share them carefully.

## API Surface

All export endpoints accept the same masking and anonymization options:

```text
GET /api/export/json?mask_sensitive=true&mask_terms=Alice,Beijing
GET /api/export/csv?mask_sensitive=true&mask_terms=Alice,Beijing
GET /api/export/report?mask_sensitive=true&mask_terms=Alice,Beijing
GET /api/export/markdown?mask_sensitive=true&mask_terms=Alice,Beijing
GET /api/export/html?mask_sensitive=true&mask_terms=Alice,Beijing
GET /api/export/json?anonymize=true
GET /api/export/html?anonymize=true&mask_sensitive=true&mask_terms=Alice,Beijing
```

`mask_terms` accepts comma-separated or newline-separated values.

`anonymize=true` can be used by itself, or together with `mask_sensitive=true`. When both are enabled, anonymization is applied first and masking is applied to the anonymized export payload.

## Accepted Risks

- False negatives are possible for informal names, aliases, partial addresses, non-Chinese phone numbers, and unusual ID formats.
- False positives are possible for strings that resemble names, addresses, IDs, emails, or local file paths.
- Anonymized exports may still reveal sensitive context through timestamps, message volume, message type patterns, or unrecognized sensitive text.
- Export encryption is a separate roadmap item and is not provided by masking.
