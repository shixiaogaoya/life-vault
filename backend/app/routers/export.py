import csv
from io import StringIO
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.db import query_messages


router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/csv")
async def export_csv(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
) -> StreamingResponse:
    """导出消息为 CSV 格式"""
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
        writer.writerow(message.to_dict())

    csv_content = output.getvalue()
    output.close()

    return StreamingResponse(
        iter([csv_content.encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=messages_{filters.get('chat_id', 'all')}.csv"
        },
    )


@router.get("/json")
async def export_json(
    chat_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
) -> dict[str, Any]:
    """导出消息为 JSON 格式"""
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
        messages = await query_messages(filters, page=1, page_size=100000)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc

    return {
        "total": len(messages),
        "filters": filters,
        "messages": [message.to_dict() for message in messages],
    }
