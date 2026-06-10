import json
import logging
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.adapters.wechat import ImportErrorRecord, parse_wechat_export
from app.db import insert_messages
from app.models.message import MessageSource, UnifiedMessage


logger = logging.getLogger("lifevault.import")
router = APIRouter(prefix="/api", tags=["import"])


class ImportRequest(BaseModel):
    source: str = Field(min_length=1)
    db_path: str = Field(min_length=1)
    contact_db_path: str = Field(min_length=1)


class ImportErrorItem(BaseModel):
    local_id: int | None = None
    error_type: str
    error_message: str


class ImportResponse(BaseModel):
    success: bool
    total_messages: int = Field(ge=0)
    imported: int = Field(ge=0)
    failed: int = Field(ge=0)
    errors: list[ImportErrorItem]


@router.post("/import", response_model=ImportResponse)
async def import_messages(request: Request) -> ImportResponse:
    """导入数据。

    支持两种 v0.1.x 路径：
    - multipart/form-data 上传 LifeVault JSON 导出/示例数据（字段名 file）
    - application/json 提交 WeChat 4.x 数据库路径
    """
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        return await _import_multipart_json(request, content_type)

    try:
        raw_payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid import request") from exc

    if isinstance(raw_payload, list) or (
        isinstance(raw_payload, dict) and isinstance(raw_payload.get("messages"), list)
    ):
        return await _import_lifevault_json(raw_payload)

    try:
        payload = ImportRequest.model_validate(raw_payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid import request") from exc

    return await _import_wechat_paths(payload)


async def _import_wechat_paths(payload: ImportRequest) -> ImportResponse:
    if payload.source != MessageSource.WECHAT_4X.value:
        raise HTTPException(status_code=400, detail="unsupported source")
    if not Path(payload.db_path).is_file():
        raise HTTPException(status_code=400, detail="db_path does not exist")
    if not Path(payload.contact_db_path).is_file():
        raise HTTPException(status_code=400, detail="contact_db_path does not exist")

    try:
        messages, errors = await parse_wechat_export(payload.db_path, payload.contact_db_path)
        imported = await insert_messages(messages)
    except aiosqlite.Error as exc:
        raise HTTPException(status_code=500, detail="database connection failed") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc

    total_messages = len(messages) + len(errors)
    failed = len(errors)
    if total_messages and failed / total_messages > 0.1:
        logger.error(
            "Import parse failure rate exceeded 10%%: failed=%s total=%s",
            failed,
            total_messages,
        )

    return ImportResponse(
        success=True,
        total_messages=total_messages,
        imported=imported,
        failed=failed,
        errors=[_to_error_item(error) for error in errors],
    )


async def _import_multipart_json(request: Request, content_type: str) -> ImportResponse:
    body = await request.body()
    file_bytes = _extract_multipart_file(body, content_type)

    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="import file must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON import file") from exc

    return await _import_lifevault_json(payload)


async def _import_lifevault_json(payload: Any) -> ImportResponse:
    if isinstance(payload, dict):
        records = payload.get("messages")
    elif isinstance(payload, list):
        records = payload
    else:
        records = None

    if not isinstance(records, list):
        raise HTTPException(status_code=400, detail="JSON import file must contain messages")

    messages: list[UnifiedMessage] = []
    errors: list[ImportErrorRecord] = []
    for index, record in enumerate(records):
        try:
            if not isinstance(record, dict):
                raise ValueError("message record must be an object")
            messages.append(UnifiedMessage.from_dict(record))
        except Exception as exc:
            errors.append(
                ImportErrorRecord(
                    local_id=record.get("local_id") if isinstance(record, dict) else None,
                    error_type="validation_error",
                    error_message=f"message[{index}]: {exc}",
                    raw_data=record if isinstance(record, dict) else {"value": record},
                )
            )

    try:
        imported = await insert_messages(messages)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc

    return ImportResponse(
        success=True,
        total_messages=len(records),
        imported=imported,
        failed=len(errors),
        errors=[_to_error_item(error) for error in errors],
    )


def _extract_multipart_file(body: bytes, content_type: str) -> bytes:
    boundary_marker = "boundary="
    if boundary_marker not in content_type:
        raise HTTPException(status_code=400, detail="multipart boundary missing")

    boundary = content_type.split(boundary_marker, 1)[1].strip().strip('"')
    if not boundary:
        raise HTTPException(status_code=400, detail="multipart boundary missing")

    delimiter = f"--{boundary}".encode("utf-8")
    for part in body.split(delimiter):
        if b'name="file"' not in part:
            continue
        header_end = part.find(b"\r\n\r\n")
        if header_end < 0:
            raise HTTPException(status_code=400, detail="invalid multipart file")
        content = part[header_end + 4 :]
        if content.endswith(b"\r\n"):
            return content[:-2]
        return content

    raise HTTPException(status_code=400, detail="file field is required")


def _to_error_item(error: ImportErrorRecord) -> ImportErrorItem:
    return ImportErrorItem(
        local_id=error.local_id,
        error_type=error.error_type,
        error_message=error.error_message,
    )
