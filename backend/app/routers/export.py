import csv
import base64
import html
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone, timedelta
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
from app.utils.text import extract_text_tokens, is_emoji_char


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
            "visualization": _empty_visualization(),
            "messages": [],
        }

    # 消息类型分布
    type_distribution: dict[str, int] = {}
    sender_distribution: dict[str, int] = {}
    earliest_timestamp = messages[0].timestamp
    latest_timestamp = messages[0].timestamp

    # 可视化数据
    tz_offset = _get_export_tz_offset()
    tz = timezone(timedelta(hours=tz_offset))
    heatmap = [[0] * 24 for _ in range(7)]
    hourly = [0] * 24
    weekday_dist = [0] * 7
    daily_counter: dict[str, int] = {}
    emoji_counter: Counter = Counter()
    term_counter: Counter = Counter()
    sent_count = 0
    received_count = 0

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

        # 时区敏感的可视化数据
        try:
            local_dt = datetime.fromtimestamp(msg.timestamp, tz=tz)
            iso_wday = local_dt.weekday()  # 0=Monday
            hour = local_dt.hour
            heatmap[iso_wday][hour] += 1
            hourly[hour] += 1
            weekday_dist[iso_wday] += 1
            day_key = local_dt.strftime("%Y-%m-%d")
            daily_counter[day_key] = daily_counter.get(day_key, 0) + 1
        except (OSError, ValueError, OverflowError):
            pass

        # 发送/接收
        if msg.is_sender:
            sent_count += 1
        else:
            received_count += 1

        # Emoji / 词频（仅文本类消息，使用导出后的内容以反映脱敏状态）
        if msg.msg_type == 1:
            content = str(exported.get("content") or "")
            for ch in content:
                if is_emoji_char(ch):
                    emoji_counter[ch] += 1
            for token in extract_text_tokens(content):
                term_counter[token] += 1

    # Top 10 发送者
    top_senders = sorted(
        [{"name": k, "count": v} for k, v in sender_distribution.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    daily_timeseries = sorted(
        ({"date": k, "count": v} for k, v in daily_counter.items()),
        key=lambda x: x["date"],
    )

    heatmap_max = max((max(row) for row in heatmap), default=0)
    total_sr = sent_count + received_count

    visualization = {
        "activity_heatmap": {
            "matrix": heatmap,
            "max_count": heatmap_max,
            "weekday_labels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
        },
        "hourly_distribution": hourly,
        "weekday_distribution": weekday_dist,
        "daily_timeseries": daily_timeseries,
        "emoji_stats": [
            {"emoji": k, "count": v} for k, v in emoji_counter.most_common(20)
        ],
        "top_terms": [
            {"term": k, "count": v} for k, v in term_counter.most_common(30)
        ],
        "sender_receiver_ratio": {
            "sent": sent_count,
            "received": received_count,
            "sent_percentage": round(sent_count * 100.0 / total_sr, 2) if total_sr else 0.0,
        },
        "timezone_offset": tz_offset,
    }

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
        "visualization": visualization,
        "messages": exported_messages,
    }


def _empty_visualization() -> dict[str, Any]:
    return {
        "activity_heatmap": {
            "matrix": [[0] * 24 for _ in range(7)],
            "max_count": 0,
            "weekday_labels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
        },
        "hourly_distribution": [0] * 24,
        "weekday_distribution": [0] * 7,
        "daily_timeseries": [],
        "emoji_stats": [],
        "top_terms": [],
        "sender_receiver_ratio": {"sent": 0, "received": 0, "sent_percentage": 0.0},
        "timezone_offset": _get_export_tz_offset(),
    }


def _get_export_tz_offset() -> int:
    """获取报告用的时区偏移（与 stats API 保持一致）"""
    raw = os.getenv("LIFEVAULT_TIMEZONE_OFFSET", "8")
    try:
        offset = int(raw)
    except (TypeError, ValueError):
        return 8
    return offset if -12 <= offset <= 14 else 8


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
    visualization = report.get("visualization") or _empty_visualization()
    type_rows = "\n".join(
        f"<tr><td>{html.escape(str(type_name))}</td><td>{count}</td></tr>"
        for type_name, count in summary["message_types"].items()
    ) or '<tr><td colspan="2">No messages</td></tr>'
    sender_items = "\n".join(
        f"<li>{html.escape(str(item['name'] or 'Unknown'))}: {item['count']}</li>"
        for item in summary["top_senders"]
    ) or "<li>No senders</li>"
    message_items = "\n".join(_render_html_message(message) for message in report["messages"])

    # 内嵌 SVG 可视化（无外网依赖）
    hourly_svg = _render_hourly_svg(visualization["hourly_distribution"])
    weekday_svg = _render_weekday_svg(
        visualization["weekday_distribution"],
        visualization["activity_heatmap"]["weekday_labels"],
    )
    timeline_svg = _render_timeline_svg(visualization["daily_timeseries"])
    heatmap_html = _render_heatmap_html(visualization["activity_heatmap"])
    emoji_html = _render_emoji_html(visualization["emoji_stats"])
    terms_html = _render_terms_html(visualization["top_terms"])
    sr_html = _render_sender_receiver_html(visualization["sender_receiver_ratio"])

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
    .viz-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0; }}
    .viz-card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }}
    .viz-card.full {{ grid-column: 1 / -1; }}
    .heatmap {{ display: grid; grid-template-columns: 60px repeat(24, 1fr); gap: 2px; font-size: 10px; }}
    .heatmap .cell {{ aspect-ratio: 1; border-radius: 2px; }}
    .heatmap .label {{ color: #6b7280; align-self: center; }}
    .terms-cloud {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .terms-cloud span {{ display: inline-block; padding: 4px 10px; border-radius: 12px; background: #eef2ff; color: #4338ca; font-weight: 500; }}
    .emoji-list {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .emoji-list .item {{ display: flex; align-items: center; gap: 6px; background: #fdf2f8; padding: 4px 10px; border-radius: 10px; }}
    .emoji-list .item span.emoji {{ font-size: 22px; }}
    .sr-bar {{ display: flex; height: 28px; border-radius: 6px; overflow: hidden; }}
    .sr-bar .sent {{ background: #3b82f6; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; }}
    .sr-bar .received {{ background: #e5e7eb; color: #374151; display: flex; align-items: center; justify-content: center; font-size: 12px; }}
    .legend {{ display: flex; gap: 4px; align-items: center; justify-content: flex-end; margin-top: 8px; font-size: 11px; color: #6b7280; }}
    .legend .swatch {{ width: 12px; height: 12px; border-radius: 2px; }}
    @media (max-width: 720px) {{
      .viz-grid {{ grid-template-columns: 1fr; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      .viz-card, .card, .message {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>LifeVault Export Report</h1>
    <p class="muted">Generated as a self-contained local report · UTC{visualization['timezone_offset'] >= 0 and '+' or ''}{visualization['timezone_offset']}</p>
    <section class="grid">
      <div class="card"><div class="muted">Total messages</div><div class="metric">{summary['total_messages']}</div></div>
      <div class="card"><div class="muted">Date range</div><div>{html.escape(_format_timestamp(summary['date_range']['earliest']))}<br>{html.escape(_format_timestamp(summary['date_range']['latest']))}</div></div>
      <div class="card"><div class="muted">Privacy masking</div><div>{'Enabled' if privacy['enabled'] else 'Disabled'}</div></div>
      <div class="card"><div class="muted">Sharing anonymization</div><div>{'Enabled' if anonymization['enabled'] else 'Disabled'}</div></div>
    </section>

    <h2>Visualization</h2>
    <div class="viz-grid">
      <div class="viz-card full">
        <h3 style="margin-top:0">Activity Heatmap</h3>
        {heatmap_html}
      </div>
      <div class="viz-card">
        <h3 style="margin-top:0">Hourly Distribution</h3>
        {hourly_svg}
      </div>
      <div class="viz-card">
        <h3 style="margin-top:0">Weekday Distribution</h3>
        {weekday_svg}
      </div>
      <div class="viz-card full">
        <h3 style="margin-top:0">Daily Timeline</h3>
        {timeline_svg}
      </div>
      <div class="viz-card">
        <h3 style="margin-top:0">Sender / Receiver</h3>
        {sr_html}
      </div>
      <div class="viz-card">
        <h3 style="margin-top:0">Top Terms</h3>
        {terms_html}
      </div>
      <div class="viz-card full">
        <h3 style="margin-top:0">Top Emoji</h3>
        {emoji_html}
      </div>
    </div>

    <h2>Message Types</h2>
    <table><thead><tr><th>Type</th><th>Count</th></tr></thead><tbody>{type_rows}</tbody></table>
    <h2>Top Senders</h2>
    <ul>{sender_items}</ul>
    <h2>Messages</h2>
    {message_items or '<p class="muted">No messages.</p>'}
  </main>
</body>
</html>"""


def _heatmap_color(count: int, max_count: int) -> str:
    if count == 0 or max_count == 0:
        return "#f3f4f6"
    intensity = (count / max_count) ** 0.7  # 非线性增强中间层次
    hue = 220 - intensity * 40
    lightness = 90 - intensity * 50
    return f"hsl({hue:.0f}, 65%, {lightness:.0f}%)"


def _render_heatmap_html(heatmap: dict[str, Any]) -> str:
    matrix = heatmap["matrix"]
    max_count = heatmap["max_count"]
    labels = heatmap["weekday_labels"]

    if max_count == 0:
        return '<p class="muted">No data</p>'

    header = '<div class="label"></div>' + ''.join(
        f'<div class="label" style="text-align:center">{h if h % 4 == 0 else ""}</div>'
        for h in range(24)
    )
    rows = []
    for w_idx, row in enumerate(matrix):
        cells = ''.join(
            f'<div class="cell" style="background:{_heatmap_color(c, max_count)}" title="{labels[w_idx]} {h:02d}:00 · {c}"></div>'
            for h, c in enumerate(row)
        )
        rows.append(f'<div class="label">{labels[w_idx]}</div>{cells}')

    legend = (
        '<div class="legend"><span>Less</span>'
        + ''.join(
            f'<div class="swatch" style="background:{_heatmap_color(int(max_count * ratio), max_count)}"></div>'
            for ratio in (0.05, 0.25, 0.5, 0.75, 1.0)
        )
        + '<span>More</span></div>'
    )
    return f'<div class="heatmap" style="overflow-x:auto">{header}{"".join(rows)}</div>{legend}'


def _render_hourly_svg(hourly: list[int]) -> str:
    if not hourly or max(hourly) == 0:
        return '<p class="muted">No data</p>'
    max_val = max(hourly)
    bar_width = 18
    gap = 4
    width = 24 * (bar_width + gap) + 40
    height = 140
    bars = []
    for i, val in enumerate(hourly):
        bar_height = (val / max_val) * (height - 40)
        x = 30 + i * (bar_width + gap)
        y = height - 20 - bar_height
        bar_color = "#3b82f6" if val < max_val * 0.7 else "#1d4ed8"
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" fill="{bar_color}" rx="2">'
            f'<title>{i:02d}:00 · {val}</title></rect>'
        )
    labels = ''.join(
        f'<text x="{30 + i * (bar_width + gap) + bar_width/2:.1f}" y="{height - 6}" font-size="9" fill="#9ca3af" text-anchor="middle">{i if i % 6 == 0 else ""}</text>'
        for i in range(24)
    )
    return f'<svg viewBox="0 0 {width} {height}" style="width:100%;height:auto">{"".join(bars)}{labels}</svg>'


def _render_weekday_svg(weekday: list[int], labels: list[str]) -> str:
    if not weekday or max(weekday) == 0:
        return '<p class="muted">No data</p>'
    max_val = max(weekday)
    bar_width = 40
    gap = 12
    width = 7 * (bar_width + gap) + 40
    height = 140
    bars = []
    for i, val in enumerate(weekday):
        bar_height = (val / max_val) * (height - 40)
        x = 20 + i * (bar_width + gap)
        y = height - 20 - bar_height
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" fill="#10b981" rx="2">'
            f'<title>{labels[i]} · {val}</title></rect>'
        )
        bars.append(
            f'<text x="{x + bar_width/2:.1f}" y="{height - 6}" font-size="10" fill="#6b7280" text-anchor="middle">{labels[i]}</text>'
        )
    return f'<svg viewBox="0 0 {width} {height}" style="width:100%;height:auto">{"".join(bars)}</svg>'


def _render_timeline_svg(timeseries: list[dict[str, Any]]) -> str:
    if not timeseries:
        return '<p class="muted">No data</p>'
    width = 600
    height = 120
    padding = 12
    max_count = max((d["count"] for d in timeseries), default=1) or 1
    step_x = (width - padding * 2) / max(len(timeseries) - 1, 1)

    points = []
    for i, d in enumerate(timeseries):
        x = padding + i * step_x
        y = height - padding - (d["count"] / max_count) * (height - padding * 2)
        points.append((x, y, d))

    if not points:
        return '<p class="muted">No data</p>'

    line_path = " ".join(
        f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}" for i, (x, y, _) in enumerate(points)
    )
    area_path = (
        f"{line_path} L{points[-1][0]:.2f},{height - padding} "
        f"L{points[0][0]:.2f},{height - padding} Z"
    )
    circles = "".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="#4f46e5"><title>{d["date"]} · {d["count"]}</title></circle>'
        for x, y, d in points
    )
    first_date = timeseries[0]["date"]
    last_date = timeseries[-1]["date"]
    return (
        f'<svg viewBox="0 0 {width} {height}" style="width:100%;height:auto">'
        f'<defs><linearGradient id="area-grad" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="rgba(99,102,241,0.4)" />'
        f'<stop offset="100%" stop-color="rgba(99,102,241,0)" />'
        f'</linearGradient></defs>'
        f'<path d="{area_path}" fill="url(#area-grad)" />'
        f'<path d="{line_path}" fill="none" stroke="rgb(79,70,229)" stroke-width="2" stroke-linejoin="round" />'
        f'{circles}'
        f'<text x="{padding}" y="12" font-size="10" fill="#9ca3af">peak {max_count}</text>'
        f'<text x="{padding}" y="{height - 1}" font-size="10" fill="#9ca3af">{first_date}</text>'
        f'<text x="{width - padding}" y="{height - 1}" font-size="10" fill="#9ca3af" text-anchor="end">{last_date}</text>'
        f'</svg>'
    )


def _render_emoji_html(emoji_stats: list[dict[str, Any]]) -> str:
    if not emoji_stats:
        return '<p class="muted">No emoji detected</p>'
    items = "".join(
        f'<div class="item"><span class="emoji">{html.escape(item["emoji"])}</span><span>{item["count"]}</span></div>'
        for item in emoji_stats[:20]
    )
    return f'<div class="emoji-list">{items}</div>'


def _render_terms_html(top_terms: list[dict[str, Any]]) -> str:
    if not top_terms:
        return '<p class="muted">No terms detected</p>'
    items = "".join(
        f'<span>{html.escape(str(item["term"]))} <em style="opacity:0.6;font-style:normal">{item["count"]}</em></span>'
        for item in top_terms[:30]
    )
    return f'<div class="terms-cloud">{items}</div>'


def _render_sender_receiver_html(sr: dict[str, Any]) -> str:
    sent = sr["sent"]
    received = sr["received"]
    total = sent + received
    if total == 0:
        return '<p class="muted">No data</p>'
    sent_pct = sr["sent_percentage"]
    received_pct = 100 - sent_pct
    sent_label = f"Sent {sent_pct:.1f}%" if sent_pct >= 8 else ""
    received_label = f"Received {received_pct:.1f}%" if received_pct >= 8 else ""
    return (
        f'<div class="sr-bar">'
        f'<div class="sent" style="width:{sent_pct:.2f}%">{sent_label}</div>'
        f'<div class="received" style="width:{received_pct:.2f}%">{received_label}</div>'
        f'</div>'
        f'<p class="muted" style="margin-top:8px">Sent {sent} · Received {received} · Total {total}</p>'
    )


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
