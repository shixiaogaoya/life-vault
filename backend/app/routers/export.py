import csv
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

    try:
        messages = await query_messages(filters, page=1, page_size=100000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc

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

    try:
        messages = await query_messages(filters, page=1, page_size=100000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc

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

    try:
        messages = await query_messages(filters, page=1, page_size=100000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc

    # 统计分析
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

    exported_messages = [_message_to_export_dict(message, masking_options) for message in messages]

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
