import copy
import re
from dataclasses import dataclass, field
from typing import Any


PHONE_PATTERN = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
ID_CARD_PATTERN = re.compile(
    r"(?<!\d)(\d{6})(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(\d{3}[\dXx])(?!\d)"
)
EMAIL_PATTERN = re.compile(r"(?<![\w.+-])([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]*)(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![\w.+-])")
PATH_PATTERN = re.compile(
    r"(?P<path>(?:[A-Za-z]:\\[^\s\"'<>|]+)|(?:/(?:Users|home|var|tmp|mnt)/[^\s\"'<>]+))"
)


@dataclass(frozen=True)
class PrivacyMaskingOptions:
    """Configurable export-time privacy masking options."""

    enabled: bool = False
    mask_phone: bool = True
    mask_id_card: bool = True
    mask_email: bool = True
    mask_paths: bool = True
    custom_terms: tuple[str, ...] = field(default_factory=tuple)


def parse_custom_terms(value: str | None) -> tuple[str, ...]:
    """Parse comma/newline separated custom masking terms."""
    if not value:
        return ()

    terms: list[str] = []
    for raw_term in re.split(r"[\n,，]", value):
        term = raw_term.strip()
        if term and term not in terms:
            terms.append(term)
    return tuple(terms)


def masking_summary(options: PrivacyMaskingOptions) -> dict[str, Any]:
    return {
        "enabled": options.enabled,
        "rules": _enabled_rule_names(options),
        "custom_term_count": len(options.custom_terms),
    }


def mask_message_dict(message: dict[str, Any], options: PrivacyMaskingOptions) -> dict[str, Any]:
    """Return a masked copy of a serialized UnifiedMessage dict."""
    if not options.enabled:
        return message

    masked = copy.deepcopy(message)
    masked = _mask_value(masked, options)
    if isinstance(masked, dict):
        metadata = masked.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        metadata["privacy_masking"] = masking_summary(options)
        masked["metadata"] = metadata
    return masked


def mask_text(text: str, options: PrivacyMaskingOptions) -> str:
    if not options.enabled or not text:
        return text

    masked = text
    for term in sorted(options.custom_terms, key=len, reverse=True):
        masked = masked.replace(term, "[MASKED]")

    if options.mask_phone:
        masked = PHONE_PATTERN.sub(_mask_phone, masked)
    if options.mask_id_card:
        masked = ID_CARD_PATTERN.sub(r"\1********\2", masked)
    if options.mask_email:
        masked = EMAIL_PATTERN.sub(r"\1***\3", masked)
    if options.mask_paths:
        masked = PATH_PATTERN.sub("[PATH]", masked)

    return masked


def _mask_value(value: Any, options: PrivacyMaskingOptions) -> Any:
    if isinstance(value, str):
        return mask_text(value, options)
    if isinstance(value, list):
        return [_mask_value(item, options) for item in value]
    if isinstance(value, tuple):
        return tuple(_mask_value(item, options) for item in value)
    if isinstance(value, dict):
        return {key: _mask_value(item, options) for key, item in value.items()}
    return value


def _mask_phone(match: re.Match[str]) -> str:
    value = match.group(1)
    return f"{value[:3]}****{value[-4:]}"


def _enabled_rule_names(options: PrivacyMaskingOptions) -> list[str]:
    if not options.enabled:
        return []

    rules: list[str] = []
    if options.mask_phone:
        rules.append("phone")
    if options.mask_id_card:
        rules.append("id_card")
    if options.mask_email:
        rules.append("email")
    if options.mask_paths:
        rules.append("path")
    if options.custom_terms:
        rules.append("custom_terms")
    return rules
