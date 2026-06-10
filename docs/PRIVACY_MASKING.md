# Privacy Masking Design

**Last updated:** 2026-06-10

## Goal

Export masking reduces accidental exposure when users share LifeVault exports or reports. It is an export-time protection layer: the original local SQLite database remains unchanged.

## Threat Model

Masking is designed to reduce exposure of common personal identifiers in exported JSON, CSV, and report payloads:

- Chinese mobile phone numbers
- Chinese resident ID cards
- Email addresses
- Common local file paths
- Chinese names detected from message sender/chat fields
- Common Chinese address-like text fragments
- User-provided custom terms such as names, addresses, company names, or aliases

## Security Boundary

- Masking applies only when `mask_sensitive=true` is passed to an export endpoint.
- Masking is deterministic string replacement, not cryptographic anonymization.
- The local database, in-memory query results, and original imported records remain unmodified.
- Name/address detection is conservative and rule-based; custom terms are still recommended for names, aliases, and addresses that do not match the built-in patterns.
- Masked exports are still unencrypted files; users should store and share them carefully.

## API Surface

All export endpoints accept the same masking options:

```text
GET /api/export/json?mask_sensitive=true&mask_terms=Alice,Beijing
GET /api/export/csv?mask_sensitive=true&mask_terms=Alice,Beijing
GET /api/export/report?mask_sensitive=true&mask_terms=Alice,Beijing
GET /api/export/markdown?mask_sensitive=true&mask_terms=Alice,Beijing
GET /api/export/html?mask_sensitive=true&mask_terms=Alice,Beijing
```

`mask_terms` accepts comma-separated or newline-separated values.

## Accepted Risks

- False negatives are possible for informal names, aliases, partial addresses, non-Chinese phone numbers, and unusual ID formats.
- False positives are possible for strings that resemble names, addresses, IDs, emails, or local file paths.
- Export encryption is a separate roadmap item and is not provided by masking.
