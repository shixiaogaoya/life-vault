from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import count_messages, get_message_by_id, query_messages
from app.models.message import UnifiedMessage


router = APIRouter(prefix="/api", tags=["messages"])


class MessageListItem(BaseModel):
    """消息列表项（简化版）"""
    id: int
    msg_type: int
    sub_type: int
    timestamp: int
    chat_id: str
    chat_name: str = ""
    sender_name: str = ""
    is_sender: bool = False
    content: str = ""
    type_name: str


class MessageListResponse(BaseModel):
    """消息列表响应"""
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=10, le=200)
    messages: list[MessageListItem]


@router.get("/messages", response_model=MessageListResponse)
async def get_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
) -> MessageListResponse:
    """分页查询消息"""
    filters = {
        key: value
        for key, value in {
            "chat_id": chat_id,
            "date_from": date_from,
            "date_to": date_to,
        }.items()
        if value is not None and value != ""
    }

    try:
        total = await count_messages(filters)
        messages = await query_messages(filters, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc

    return MessageListResponse(
        total=total,
        page=page,
        page_size=page_size,
        messages=[_to_list_item(message) for message in messages],
    )


@router.get("/messages/{id}")
async def get_message(id: int) -> dict[str, Any]:
    """查询单条消息详情"""
    try:
        message = await get_message_by_id(id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc

    data = message.to_dict()
    data["type_name"] = _type_name(message.msg_type, message.sub_type)
    return data


def _to_list_item(message: UnifiedMessage) -> MessageListItem:
    """将 UnifiedMessage 转换为列表项"""
    return MessageListItem(
        id=message.id,
        msg_type=message.msg_type,
        sub_type=message.sub_type,
        timestamp=message.timestamp,
        chat_id=message.chat_id,
        chat_name=message.chat_name,
        sender_name=message.sender_name,
        is_sender=message.is_sender,
        content=message.content,
        type_name=_type_name(message.msg_type, message.sub_type),
    )


def _type_name(msg_type: int, sub_type: int = 0) -> str:
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
