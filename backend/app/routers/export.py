import csv
import html
import re
from datetime import datetime
from io import StringIO
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.db import query_messages
from app.models.message import UnifiedMessage
from app.privacy.masking import (
    PrivacyMaskingOptions,
    mask_message_dict,
    masking_summary,
    parse_custom_terms,
)


router = APIRouter(prefix="/api/export", tags=["export"])


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
) -> StreamingResponse:
    """导出消息为 CSV 格式"""
    filters = _build_filters(chat_id, date_from, date_to)
    masking_options = _build_masking_options(mask_sensitive, mask_terms)
    messages = await _query_export_messages(filters)

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
        writer.writerow(_message_to_export_dict(message, masking_options))

    csv_content = output.getvalue()
    output.close()

    return StreamingResponse(
        iter([csv_content.encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=messages_{_filename_scope(filters, masking_options)}.csv"
        },
    )


@router.get("/json")
async def export_json(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    mask_sensitive: bool = Query(False),
    mask_terms: str | None = Query(None),
) -> dict[str, Any]:
    """导出消息为 JSON 格式"""
    filters = _build_filters(chat_id, date_from, date_to)
    masking_options = _build_masking_options(mask_sensitive, mask_terms)
    messages = await _query_export_messages(filters)

    return {
        "total": len(messages),
        "filters": filters,
        "privacy": masking_summary(masking_options),
        "messages": [_message_to_export_dict(message, masking_options) for message in messages],
    }


@router.get("/report")
async def export_report(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    mask_sensitive: bool = Query(False),
    mask_terms: str | None = Query(None),
) -> dict[str, Any]:
    """导出数据分析报告（JSON 格式，包含统计信息）"""
    filters = _build_filters(chat_id, date_from, date_to)
    masking_options = _build_masking_options(mask_sensitive, mask_terms)
    messages = await _query_export_messages(filters)
    exported_messages = [_message_to_export_dict(message, masking_options) for message in messages]

    return _build_report_payload(messages, exported_messages, filters, masking_options)


@router.get("/markdown")
async def export_markdown(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    mask_sensitive: bool = Query(False),
    mask_terms: str | None = Query(None),
) -> StreamingResponse:
    """导出消息为 Markdown 聊天记录"""
    filters = _build_filters(chat_id, date_from, date_to)
    masking_options = _build_masking_options(mask_sensitive, mask_terms)
    messages = await _query_export_messages(filters)
    exported_messages = [_message_to_export_dict(message, masking_options) for message in messages]
    report = _build_report_payload(messages, exported_messages, filters, masking_options)
    content = _render_markdown_export(report)

    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=messages_{_filename_scope(filters, masking_options)}.md"
        },
    )


@router.get("/html")
async def export_html(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    mask_sensitive: bool = Query(False),
    mask_terms: str | None = Query(None),
) -> StreamingResponse:
    """导出自包含 HTML 分析报告"""
    filters = _build_filters(chat_id, date_from, date_to)
    masking_options = _build_masking_options(mask_sensitive, mask_terms)
    messages = await _query_export_messages(filters)
    exported_messages = [_message_to_export_dict(message, masking_options) for message in messages]
    report = _build_report_payload(messages, exported_messages, filters, masking_options)
    content = _render_html_export(report)

    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=messages_{_filename_scope(filters, masking_options)}.html"
        },
    )


def _build_report_payload(
    messages: list[UnifiedMessage],
    exported_messages: list[dict[str, Any]],
    filters: dict[str, str],
    masking_options: PrivacyMaskingOptions,
) -> dict[str, Any]:
    total_messages = len(messages)
    if total_messages == 0:
        return {
            "filters": filters,
            "privacy": masking_summary(masking_options),
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
    lines = [
        "# LifeVault Chat Export",
        "",
        "## Summary",
        "",
        f"- Total messages: {summary['total_messages']}",
        f"- Date range: {_format_timestamp(summary['date_range']['earliest'])} - {_format_timestamp(summary['date_range']['latest'])}",
        f"- Privacy masking: {'enabled' if privacy['enabled'] else 'disabled'}",
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


def _message_to_export_dict(
    message: UnifiedMessage,
    masking_options: PrivacyMaskingOptions,
) -> dict[str, Any]:
    return mask_message_dict(message.to_dict(), masking_options)


def _filename_scope(filters: dict[str, str], masking_options: PrivacyMaskingOptions) -> str:
    scope = filters.get("chat_id", "all")
    return f"{scope}_masked" if masking_options.enabled else scope


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
