import logging
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.adapters.wechat import ImportErrorRecord, parse_wechat_export
from app.db import insert_messages
from app.models.message import MessageSource


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
async def import_messages(request: ImportRequest) -> ImportResponse:
    if request.source != MessageSource.WECHAT_4X.value:
        raise HTTPException(status_code=400, detail="unsupported source")
    if not Path(request.db_path).is_file():
        raise HTTPException(status_code=400, detail="db_path does not exist")
    if not Path(request.contact_db_path).is_file():
        raise HTTPException(status_code=400, detail="contact_db_path does not exist")

    try:
        messages, errors = await parse_wechat_export(request.db_path, request.contact_db_path)
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


def _to_error_item(error: ImportErrorRecord) -> ImportErrorItem:
    return ImportErrorItem(
        local_id=error.local_id,
        error_type=error.error_type,
        error_message=error.error_message,
    )
