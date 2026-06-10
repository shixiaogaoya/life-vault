import base64
import re
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

from app.db import insert_import_errors
from app.models.message import MessageSource, UnifiedMessage


@dataclass
class ImportErrorRecord:
    local_id: int | None
    error_type: str
    error_message: str
    raw_data: dict[str, Any]
    source: str = MessageSource.WECHAT_4X.value
    timestamp: int = 0
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = int(datetime.now().timestamp())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def parse_wechat_export(
    msg_db_path: str,
    contact_db_path: str,
) -> tuple[list[UnifiedMessage], list[ImportErrorRecord]]:
    """Parse WeChat 4.x MSG.db and MicroMsg.db into UnifiedMessage objects."""
    contact_map = await _load_contacts(contact_db_path)
    messages: list[UnifiedMessage] = []
    errors: list[ImportErrorRecord] = []

    async with _connect_readonly(msg_db_path) as msg_db:
        cursor = await msg_db.execute("SELECT * FROM MSG")
        rows = await cursor.fetchall()
        await cursor.close()

    for row in rows:
        row_data = _normalize_row(row)
        try:
            messages.append(_row_to_message(row_data, contact_map))
        except Exception as exc:
            errors.append(
                ImportErrorRecord(
                    local_id=_safe_int(_get(row_data, "localId", "local_id", "LocalId", "id")),
                    error_type="parse_error",
                    error_message=str(exc),
                    raw_data=_json_safe(row_data),
                )
            )

    await insert_import_errors([error.to_dict() for error in errors])
    return messages, errors


async def _load_contacts(contact_db_path: str) -> dict[str, dict[str, str]]:
    contacts: dict[str, dict[str, str]] = {}

    async with _connect_readonly(contact_db_path) as contact_db:
        columns = await _contact_table_columns(contact_db)
        if not columns:
            return contacts

        column_map = {column.lower(): column for column in columns}
        username_col = _first_existing(column_map, "username", "user_name", "wxid")
        if not username_col:
            return contacts

        optional_cols = [
            column
            for column in (
                username_col,
                _first_existing(column_map, "remark"),
                _first_existing(column_map, "nick_name", "nickname"),
                _first_existing(column_map, "alias"),
            )
            if column
        ]
        sql = f"SELECT {', '.join(optional_cols)} FROM Contact"
        cursor = await contact_db.execute(sql)
        rows = await cursor.fetchall()
        await cursor.close()

    for row in rows:
        data = _normalize_row(row)
        username = str(_get(data, "username", "user_name", "wxid") or "")
        if not username:
            continue
        remark = str(_get(data, "remark") or "")
        nick_name = str(_get(data, "nick_name", "nickname") or "")
        alias = str(_get(data, "alias") or "")
        contacts[username] = {
            "username": username,
            "name": remark or nick_name or alias or username,
            "remark": remark,
            "nick_name": nick_name,
            "alias": alias,
        }

    return contacts


async def _contact_table_columns(db: aiosqlite.Connection) -> list[str]:
    cursor = await db.execute('PRAGMA table_info("Contact")')
    rows = await cursor.fetchall()
    await cursor.close()
    return [row["name"] for row in rows]


def _row_to_message(row: dict[str, Any], contact_map: dict[str, dict[str, str]]) -> UnifiedMessage:
    local_id = _required_int(row, "localId", "local_id", "LocalId", "id")
    msg_svr_id = _required_int(row, "MsgSvrID", "msg_svr_id", "msgSvrId", "server_id")
    msg_type = _required_int(row, "Type", "msg_type", "type")
    timestamp = _required_int(row, "CreateTime", "create_time", "timestamp")
    chat_id = str(_get(row, "StrTalker", "TalkerId", "talker_id", "chat_id") or "")
    if not chat_id:
        raise ValueError("missing chat_id")

    sub_type = _safe_int(_get(row, "SubType", "sub_type")) or 0
    is_sender = bool(_safe_int(_get(row, "IsSender", "is_sender")) or 0)
    status = _safe_int(_get(row, "Status", "status")) or 0
    str_content = str(_get(row, "StrContent", "str_content", "content") or "")
    display_content = str(_get(row, "DisplayContent", "display_content") or "")

    sender_id, sender_name, content = _parse_sender(chat_id, str_content, is_sender, contact_map)
    chat_name = contact_map.get(chat_id, {}).get("name", "")

    return UnifiedMessage(
        id=0,
        source=MessageSource.WECHAT_4X,
        msg_svr_id=msg_svr_id,
        local_id=local_id,
        msg_type=msg_type,
        sub_type=sub_type,
        timestamp=timestamp,
        chat_id=chat_id,
        chat_name=chat_name,
        sender_id=sender_id,
        sender_name=sender_name,
        is_sender=is_sender,
        content=content,
        status=status,
        raw=_json_safe(row),
        metadata={
            "display_content": display_content,
            "bytes_extra": _encode_blob(_get(row, "BytesExtra", "bytes_extra")),
            "compress_content": _encode_blob(_get(row, "CompressContent", "compress_content")),
        },
    )


def _parse_sender(
    chat_id: str,
    content: str,
    is_sender: bool,
    contact_map: dict[str, dict[str, str]],
) -> tuple[str, str, str]:
    if is_sender:
        return "", "", content
    if not chat_id.endswith("@chatroom"):
        return chat_id, contact_map.get(chat_id, {}).get("name", ""), content

    sender_id = ""
    message_content = content
    prefix_match = re.match(r"^([^:\n]{1,128}):\n(.*)$", content, flags=re.DOTALL)
    if prefix_match:
        sender_id = prefix_match.group(1)
        message_content = prefix_match.group(2)
    else:
        xml_match = re.search(
            r'(?:username|fromusername|realchatname)=["\']([^"\']+)["\']',
            content,
        )
        if xml_match:
            sender_id = xml_match.group(1)

    sender_name = contact_map.get(sender_id, {}).get("name", "") if sender_id else ""
    return sender_id, sender_name, message_content


def _normalize_row(row: aiosqlite.Row) -> dict[str, Any]:
    return dict(row)


def _get(row: dict[str, Any], *names: str) -> Any:
    lower_map = {key.lower(): key for key in row}
    for name in names:
        key = lower_map.get(name.lower())
        if key is not None:
            return row[key]
    return None


def _required_int(row: dict[str, Any], *names: str) -> int:
    value = _safe_int(_get(row, *names))
    if value is None:
        raise ValueError(f"missing integer field: {'/'.join(names)}")
    return value


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_existing(column_map: dict[str, str], *names: str) -> str | None:
    for name in names:
        column = column_map.get(name.lower())
        if column:
            return column
    return None


def _encode_blob(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return str(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


@asynccontextmanager
async def _connect_readonly(db_path: str) -> AsyncIterator[aiosqlite.Connection]:
    uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
    async with aiosqlite.connect(uri, uri=True) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn
