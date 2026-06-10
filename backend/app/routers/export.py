import csv
import base64
import html
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from io import StringIO
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.db import query_messages
from app.models.message import UnifiedMessage
from app.privacy.masking import (
    PrivacyMaskingOptions,
    mask_message_dict,
    mask_text,
    masking_summary,
    parse_custom_terms,
)


router = APIRouter(prefix="/api/export", tags=["export"])

LOCATION_PLACEHOLDER = "[LOCATION_REMOVED]"
ENCRYPTED_EXPORT_FORMAT = "lifevault-encrypted-export-v1"
ENCRYPTION_ITERATIONS = 390000
PATH_ONLY_MASKING_OPTIONS = PrivacyMaskingOptions(
    enabled=True,
    mask_phone=False,
    mask_id_card=False,
    mask_email=False,
    mask_paths=True,
    mask_names=False,
    mask_addresses=False,
)
LOCATION_METADATA_KEYS = {
    "address",
    "coordinate",
    "coordinates",
    "gps",
    "lat",
    "latitude",
    "lng",
    "location",
    "lon",
    "longitude",
    "map",
    "poi",
    "位置",
    "地址",
    "经度",
    "纬度",
}


class ExportAnonymizer:
    def __init__(self, enabled: bool, custom_terms: tuple[str, ...] = ()) -> None:
        self.enabled = enabled
        self._people: dict[str, str] = {}
        self._chats: dict[str, str] = {}
        if enabled:
            for term in custom_terms:
                self.add_person(term)

    def add_person(self, value: str) -> None:
        name = value.strip()
        if name and name not in self._people:
            self._people[name] = f"Person {len(self._people) + 1}"

    def add_person_aliases(self, values: tuple[str | None, ...]) -> None:
        aliases = [value.strip() for value in values if value and value.strip()]
        if not aliases:
            return

        pseudonym = next((self._people[alias] for alias in aliases if alias in self._people), None)
        if pseudonym is None:
            pseudonym = f"Person {len(self._people) + 1}"
        for alias in aliases:
            self._people[alias] = pseudonym

    def add_chat(self, value: str) -> None:
        name = value.strip()
        if name and name not in self._people and name not in self._chats:
            self._chats[name] = f"Chat {len(self._chats) + 1}"

    def apply(self, message: UnifiedMessage) -> dict[str, Any]:
        data = message.to_dict()
        if not self.enabled:
            return data

        if data.get("msg_type") == 48:
            data["content"] = LOCATION_PLACEHOLDER

        for field_name in ("raw", "metadata"):
            value = data.get(field_name)
            if isinstance(value, dict):
                data[field_name] = _strip_location_metadata(value)

        anonymized = _anonymize_value(data, self.replacements())
        if isinstance(anonymized, dict):
            metadata = anonymized.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            metadata["privacy_anonymization"] = self.summary()
            anonymized["metadata"] = metadata
        return anonymized

    def replacements(self) -> dict[str, str]:
        return {**self._people, **self._chats}

    def summary(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "pseudonym_count": len(set(self._people.values())) + len(set(self._chats.values())),
            "location_metadata_stripped": self.enabled,
            "paths_sanitized": self.enabled,
        }


async def _query_export_messages(filters: dict[str, str]) -> list[UnifiedMessage]:
    try:
        return await query_messages(filters, page=1, page_size=100000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc


@router.get("/csv")
async def export_csv(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    mask_sensitive: bool = Query(False),
    mask_terms: str | None = Query(None),
    anonymize: bool = Query(False),
    encrypt_password: str | None = Query(None),
    gpg_recipient: str | None = Query(None),
) -> StreamingResponse:
    """导出消息为 CSV 格式"""
    _validate_export_encryption(encrypt_password, gpg_recipient)
    filters = _build_filters(chat_id, date_from, date_to)
    masking_options = _build_masking_options(mask_sensitive, mask_terms)
    messages = await _query_export_messages(filters)
    anonymizer = _build_anonymizer(messages, anonymize, mask_terms)

    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "timestamp",
            "chat_id",
            "chat_name",
            "sender_name",
            "is_sender",
            "msg_type",
            "sub_type",
            "content",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    for message in messages:
        writer.writerow(_message_to_export_dict(message, masking_options, anonymizer))

    csv_content = output.getvalue()
    output.close()
    csv_bytes = csv_content.encode("utf-8-sig")
    filename_scope = _filename_scope(filters, masking_options, anonymizer)

    if encrypt_password is not None:
        encrypted = _encrypt_export_payload(csv_bytes, "csv", encrypt_password)
        return _encrypted_streaming_response(encrypted, f"messages_{filename_scope}.lvenc")
    if gpg_recipient is not None:
        encrypted = _encrypt_export_payload_with_gpg(csv_bytes, gpg_recipient)
        return _gpg_streaming_response(encrypted, f"messages_{filename_scope}.csv.gpg")

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=messages_{filename_scope}.csv"
        },
    )


@router.get("/json", response_model=None)
async def export_json(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    mask_sensitive: bool = Query(False),
    mask_terms: str | None = Query(None),
    anonymize: bool = Query(False),
    encrypt_password: str | None = Query(None),
    gpg_recipient: str | None = Query(None),
) -> dict[str, Any] | StreamingResponse:
    """导出消息为 JSON 格式"""
    _validate_export_encryption(encrypt_password, gpg_recipient)
    filters = _build_filters(chat_id, date_from, date_to)
    masking_options = _build_masking_options(mask_sensitive, mask_terms)
    messages = await _query_export_messages(filters)
    anonymizer = _build_anonymizer(messages, anonymize, mask_terms)

    payload = {
        "total": len(messages),
        "filters": filters,
        "privacy": masking_summary(masking_options),
        "anonymization": anonymizer.summary(),
        "messages": [
            _message_to_export_dict(message, masking_options, anonymizer)
            for message in messages
        ],
    }

    if encrypt_password is not None:
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        encrypted = _encrypt_export_payload(payload_bytes, "json", encrypt_password)
        filename_scope = _filename_scope(filters, masking_options, anonymizer)
        return _encrypted_streaming_response(encrypted, f"messages_{filename_scope}.lvenc")
    if gpg_recipient is not None:
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        encrypted = _encrypt_export_payload_with_gpg(payload_bytes, gpg_recipient)
        filename_scope = _filename_scope(filters, masking_options, anonymizer)
        return _gpg_streaming_response(encrypted, f"messages_{filename_scope}.json.gpg")

    return payload


@router.get("/report")
async def export_report(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    mask_sensitive: bool = Query(False),
    mask_terms: str | None = Query(None),
    anonymize: bool = Query(False),
    encrypt_password: str | None = Query(None),
    gpg_recipient: str | None = Query(None),
) -> dict[str, Any]:
    """导出数据分析报告（JSON 格式，包含统计信息）"""
    _reject_unsupported_encryption(encrypt_password, gpg_recipient)
    filters = _build_filters(chat_id, date_from, date_to)
    masking_options = _build_masking_options(mask_sensitive, mask_terms)
    messages = await _query_export_messages(filters)
    anonymizer = _build_anonymizer(messages, anonymize, mask_terms)
    exported_messages = [
        _message_to_export_dict(message, masking_options, anonymizer)
        for message in messages
    ]

    return _build_report_payload(messages, exported_messages, filters, masking_options, anonymizer)


@router.get("/markdown")
async def export_markdown(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    mask_sensitive: bool = Query(False),
    mask_terms: str | None = Query(None),
    anonymize: bool = Query(False),
    encrypt_password: str | None = Query(None),
    gpg_recipient: str | None = Query(None),
) -> StreamingResponse:
    """导出消息为 Markdown 聊天记录"""
    _reject_unsupported_encryption(encrypt_password, gpg_recipient)
    filters = _build_filters(chat_id, date_from, date_to)
    masking_options = _build_masking_options(mask_sensitive, mask_terms)
    messages = await _query_export_messages(filters)
    anonymizer = _build_anonymizer(messages, anonymize, mask_terms)
    exported_messages = [
        _message_to_export_dict(message, masking_options, anonymizer)
        for message in messages
    ]
    report = _build_report_payload(messages, exported_messages, filters, masking_options, anonymizer)
    content = _render_markdown_export(report)

    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=messages_{_filename_scope(filters, masking_options, anonymizer)}.md"
        },
    )


@router.get("/html")
async def export_html(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    mask_sensitive: bool = Query(False),
    mask_terms: str | None = Query(None),
    anonymize: bool = Query(False),
    encrypt_password: str | None = Query(None),
    gpg_recipient: str | None = Query(None),
) -> StreamingResponse:
    """导出自包含 HTML 分析报告"""
    _reject_unsupported_encryption(encrypt_password, gpg_recipient)
    filters = _build_filters(chat_id, date_from, date_to)
    masking_options = _build_masking_options(mask_sensitive, mask_terms)
    messages = await _query_export_messages(filters)
    anonymizer = _build_anonymizer(messages, anonymize, mask_terms)
    exported_messages = [
        _message_to_export_dict(message, masking_options, anonymizer)
        for message in messages
    ]
    report = _build_report_payload(messages, exported_messages, filters, masking_options, anonymizer)
    content = _render_html_export(report)

    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=messages_{_filename_scope(filters, masking_options, anonymizer)}.html"
        },
    )


def _build_report_payload(
    messages: list[UnifiedMessage],
    exported_messages: list[dict[str, Any]],
    filters: dict[str, str],
    masking_options: PrivacyMaskingOptions,
    anonymizer: ExportAnonymizer,
) -> dict[str, Any]:
    total_messages = len(messages)
    if total_messages == 0:
        return {
            "filters": filters,
            "privacy": masking_summary(masking_options),
            "anonymization": anonymizer.summary(),
            "summary": {
                "total_messages": 0,
                "date_range": {"earliest": None, "latest": None},
                "message_types": {},
                "top_senders": [],
            },
            "messages": [],
        }

    # 消息类型分布
    type_distribution: dict[str, int] = {}
    sender_distribution: dict[str, int] = {}
    earliest_timestamp = messages[0].timestamp
    latest_timestamp = messages[0].timestamp

    for msg, exported in zip(messages, exported_messages):
        # 类型统计
        type_key = _get_type_name(msg.msg_type, msg.sub_type)
        type_distribution[type_key] = type_distribution.get(type_key, 0) + 1

        # 发送者统计
        sender_key = str(exported.get("sender_name") or exported.get("sender_id") or "")
        sender_distribution[sender_key] = sender_distribution.get(sender_key, 0) + 1

        # 时间范围
        if msg.timestamp < earliest_timestamp:
            earliest_timestamp = msg.timestamp
        if msg.timestamp > latest_timestamp:
            latest_timestamp = msg.timestamp

    # Top 10 发送者
    top_senders = sorted(
        [{"name": k, "count": v} for k, v in sender_distribution.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    return {
        "filters": filters,
        "privacy": masking_summary(masking_options),
        "anonymization": anonymizer.summary(),
        "summary": {
            "total_messages": total_messages,
            "date_range": {
                "earliest": earliest_timestamp,
                "latest": latest_timestamp,
            },
            "message_types": type_distribution,
            "top_senders": top_senders,
        },
        "messages": exported_messages,
    }


def _render_markdown_export(report: dict[str, Any]) -> str:
    summary = report["summary"]
    privacy = report["privacy"]
    anonymization = report["anonymization"]
    lines = [
        "# LifeVault Chat Export",
        "",
        "## Summary",
        "",
        f"- Total messages: {summary['total_messages']}",
        f"- Date range: {_format_timestamp(summary['date_range']['earliest'])} - {_format_timestamp(summary['date_range']['latest'])}",
        f"- Privacy masking: {'enabled' if privacy['enabled'] else 'disabled'}",
        f"- Sharing anonymization: {'enabled' if anonymization['enabled'] else 'disabled'}",
        "",
        "## Message Types",
        "",
    ]

    if summary["message_types"]:
        for type_name, count in summary["message_types"].items():
            lines.append(f"- {type_name}: {count}")
    else:
        lines.append("- None")

    lines.extend(["", "## Messages", ""])
    for message in report["messages"]:
        title = " · ".join(
            value
            for value in [
                _format_timestamp(message.get("timestamp")),
                str(message.get("chat_name") or message.get("chat_id") or ""),
                str(message.get("sender_name") or message.get("sender_id") or ""),
            ]
            if value
        )
        lines.append(f"### {title or 'Message'}")
        lines.append("")
        lines.append(
            f"- Type: {_get_type_name(int(message.get('msg_type') or 0), int(message.get('sub_type') or 0))}"
        )
        lines.append(f"- Chat ID: `{message.get('chat_id', '')}`")
        lines.append("")
        lines.append(_markdown_code_block(str(message.get("content") or "")))
        lines.append("")

    return "\n".join(lines)


def _render_html_export(report: dict[str, Any]) -> str:
    summary = report["summary"]
    privacy = report["privacy"]
    anonymization = report["anonymization"]
    type_rows = "\n".join(
        f"<tr><td>{html.escape(str(type_name))}</td><td>{count}</td></tr>"
        for type_name, count in summary["message_types"].items()
    ) or '<tr><td colspan="2">No messages</td></tr>'
    sender_items = "\n".join(
        f"<li>{html.escape(str(item['name'] or 'Unknown'))}: {item['count']}</li>"
        for item in summary["top_senders"]
    ) or "<li>No senders</li>"
    message_items = "\n".join(_render_html_message(message) for message in report["messages"])

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LifeVault Export Report</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8fafc; color: #111827; }}
    main {{ max-width: 960px; margin: 0 auto; padding: 32px 20px; }}
    h1 {{ margin: 0 0 8px; font-size: 32px; }}
    h2 {{ margin-top: 32px; }}
    .muted {{ color: #6b7280; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 24px 0; }}
    .card, .message {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }}
    .metric {{ font-size: 28px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e5e7eb; }}
    td, th {{ padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #f3f4f6; padding: 12px; border-radius: 6px; }}
    .message {{ margin: 12px 0; }}
  </style>
</head>
<body>
  <main>
    <h1>LifeVault Export Report</h1>
    <p class="muted">Generated as a self-contained local report.</p>
    <section class="grid">
      <div class="card"><div class="muted">Total messages</div><div class="metric">{summary['total_messages']}</div></div>
      <div class="card"><div class="muted">Date range</div><div>{html.escape(_format_timestamp(summary['date_range']['earliest']))}<br>{html.escape(_format_timestamp(summary['date_range']['latest']))}</div></div>
      <div class="card"><div class="muted">Privacy masking</div><div>{'Enabled' if privacy['enabled'] else 'Disabled'}</div></div>
      <div class="card"><div class="muted">Sharing anonymization</div><div>{'Enabled' if anonymization['enabled'] else 'Disabled'}</div></div>
    </section>
    <h2>Message Types</h2>
    <table><thead><tr><th>Type</th><th>Count</th></tr></thead><tbody>{type_rows}</tbody></table>
    <h2>Top Senders</h2>
    <ul>{sender_items}</ul>
    <h2>Messages</h2>
    {message_items or '<p class="muted">No messages.</p>'}
  </main>
</body>
</html>"""


def _render_html_message(message: dict[str, Any]) -> str:
    timestamp = html.escape(_format_timestamp(message.get("timestamp")))
    chat = html.escape(str(message.get("chat_name") or message.get("chat_id") or "Unknown chat"))
    sender = html.escape(str(message.get("sender_name") or message.get("sender_id") or "Unknown sender"))
    type_name = html.escape(_get_type_name(int(message.get("msg_type") or 0), int(message.get("sub_type") or 0)))
    content = html.escape(str(message.get("content") or ""))

    return f"""
    <article class="message">
      <div><strong>{sender}</strong> <span class="muted">in {chat} · {timestamp} · {type_name}</span></div>
      <pre>{content}</pre>
    </article>"""


def _markdown_code_block(content: str) -> str:
    longest_run = max((len(match.group(0)) for match in re.finditer(r"`+", content)), default=0)
    fence = "`" * max(3, longest_run + 1)
    return f"{fence}text\n{content}\n{fence}"


def _format_timestamp(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    try:
        return datetime.fromtimestamp(int(value)).isoformat(sep=" ", timespec="seconds")
    except (TypeError, ValueError, OSError):
        return str(value)


def _build_filters(
    chat_id: str | None,
    date_from: str | None,
    date_to: str | None,
) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "chat_id": chat_id,
            "date_from": date_from,
            "date_to": date_to,
        }.items()
        if value is not None and value != ""
    }


def _build_masking_options(mask_sensitive: bool, mask_terms: str | None) -> PrivacyMaskingOptions:
    return PrivacyMaskingOptions(
        enabled=mask_sensitive,
        custom_terms=parse_custom_terms(mask_terms) if mask_sensitive else (),
    )


def _reject_unsupported_encryption(
    encrypt_password: str | None, gpg_recipient: str | None
) -> None:
    if encrypt_password is not None or gpg_recipient is not None:
        raise HTTPException(
            status_code=400,
            detail="Encrypted export is only supported for JSON and CSV formats",
        )


def _validate_export_encryption(
    encrypt_password: str | None, gpg_recipient: str | None
) -> None:
    if encrypt_password is not None and gpg_recipient is not None:
        raise HTTPException(
            status_code=400,
            detail="Choose either encrypt_password or gpg_recipient, not both",
        )
    if encrypt_password is not None and not encrypt_password:
        raise HTTPException(status_code=400, detail="encrypt_password must not be empty")
    if gpg_recipient is not None and not gpg_recipient.strip():
        raise HTTPException(status_code=400, detail="gpg_recipient must not be empty")


def _encrypt_export_payload(payload: bytes, payload_format: str, password: str) -> bytes:
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ENCRYPTION_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    ciphertext = Fernet(key).encrypt(payload).decode("ascii")
    envelope = {
        "format": ENCRYPTED_EXPORT_FORMAT,
        "cipher": "fernet",
        "kdf": "pbkdf2-sha256",
        "iterations": ENCRYPTION_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "payload_format": payload_format,
        "ciphertext": ciphertext,
    }
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")


def _encrypted_streaming_response(content: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.lifevault.encrypted+json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _encrypt_export_payload_with_gpg(payload: bytes, recipient: str) -> bytes:
    gpg_path = shutil.which("gpg") or shutil.which("gpg.exe")
    if not gpg_path:
        raise HTTPException(status_code=400, detail="gpg executable was not found")

    command = [
        gpg_path,
        "--batch",
        "--yes",
        "--trust-model",
        "always",
        "--encrypt",
        "--recipient",
        recipient.strip(),
        "--output",
        "-",
        "-",
    ]
    try:
        result = subprocess.run(
            command,
            input=payload,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise HTTPException(status_code=400, detail="gpg encryption failed") from exc

    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise HTTPException(status_code=400, detail=detail or "gpg encryption failed")
    return result.stdout


def _gpg_streaming_response(content: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _build_anonymizer(
    messages: list[UnifiedMessage], anonymize: bool, mask_terms: str | None
) -> ExportAnonymizer:
    anonymizer = ExportAnonymizer(anonymize, parse_custom_terms(mask_terms))
    if not anonymize:
        return anonymizer

    for message in messages:
        anonymizer.add_person_aliases((message.sender_name, message.sender_id))
        anonymizer.add_chat(message.chat_name or message.chat_id)
    return anonymizer


def _message_to_export_dict(
    message: UnifiedMessage,
    masking_options: PrivacyMaskingOptions,
    anonymizer: ExportAnonymizer,
) -> dict[str, Any]:
    return mask_message_dict(anonymizer.apply(message), masking_options)


def _filename_scope(
    filters: dict[str, str],
    masking_options: PrivacyMaskingOptions,
    anonymizer: ExportAnonymizer,
) -> str:
    scope = filters.get("chat_id", "all")
    suffixes: list[str] = []
    if masking_options.enabled:
        suffixes.append("masked")
    if anonymizer.enabled:
        suffixes.append("anonymized")
    return "_".join([scope, *suffixes]) if suffixes else scope


def _strip_location_metadata(value: dict[str, Any]) -> dict[str, Any]:
    stripped: dict[str, Any] = {}
    for key, item in value.items():
        if _is_location_key(key):
            stripped[key] = LOCATION_PLACEHOLDER
        elif isinstance(item, dict):
            stripped[key] = _strip_location_metadata(item)
        elif isinstance(item, list):
            stripped[key] = [
                _strip_location_metadata(child) if isinstance(child, dict) else child
                for child in item
            ]
        else:
            stripped[key] = item
    return stripped


def _is_location_key(key: Any) -> bool:
    key_text = str(key).strip().lower()
    return key_text in LOCATION_METADATA_KEYS or any(
        marker in key_text for marker in ("latitude", "longitude", "location")
    )


def _anonymize_value(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        anonymized = value
        for original, pseudonym in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
            anonymized = anonymized.replace(original, pseudonym)
        return mask_text(anonymized, PATH_ONLY_MASKING_OPTIONS)
    if isinstance(value, list):
        return [_anonymize_value(item, replacements) for item in value]
    if isinstance(value, tuple):
        return tuple(_anonymize_value(item, replacements) for item in value)
    if isinstance(value, dict):
        return {key: _anonymize_value(item, replacements) for key, item in value.items()}
    return value


def _get_type_name(msg_type: int, sub_type: int = 0) -> str:
    """消息类型名称映射"""
    if msg_type == 49:
        return {
            3: "音乐",
            5: "链接",
            6: "文件",
            19: "合并转发",
            33: "小程序",
            51: "视频号",
            57: "引用消息",
            2000: "转账",
        }.get(sub_type, f"应用消息({sub_type})")

    return {
        1: "文本",
        3: "图片",
        34: "语音",
        42: "名片",
        43: "视频",
        47: "表情包",
        48: "位置",
        50: "音视频通话",
        66: "OpenIM名片",
        10000: "系统消息",
    }.get(msg_type, f"未知({msg_type})")
