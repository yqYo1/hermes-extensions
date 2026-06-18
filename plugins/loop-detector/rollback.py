import os
import sqlite3
from typing import Any, Dict, List

from hermes_cli.config import get_hermes_home


def _get_db_path() -> str:
    return os.path.join(get_hermes_home(), "state.db")


def _get_message_table_name() -> str:
    """メッセージテーブル名を自動検出"""
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return "messages"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%message%'"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    # messages テーブルを優先
    for t in tables:
        if t == "messages":
            return t
    return tables[0] if tables else "messages"


def get_messages(session_id: str) -> List[Dict[str, Any]]:
    """セッションの全メッセージを取得（古い順）"""
    try:
        from hermes_state import SessionDB

        db = SessionDB()
        return db.get_messages(session_id)
    except Exception:
        pass

    # フォールバック: 直接SQLite
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return []

    table = _get_message_table_name()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            f"SELECT * FROM {table} WHERE session_id = ? ORDER BY id ASC", (session_id,)
        )
        messages = [dict(row) for row in cursor.fetchall()]
    except Exception:
        messages = []
    finally:
        conn.close()

    return messages


def delete_messages_after(session_id: str, message_index: int) -> bool:
    """指定インデックス以降のメッセージを削除"""
    messages = get_messages(session_id)
    if not messages or message_index >= len(messages):
        return False

    cutoff = messages[message_index]
    msg_id = cutoff.get("id")
    if not msg_id:
        return False

    db_path = _get_db_path()
    table = _get_message_table_name()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"DELETE FROM {table} WHERE session_id = ? AND id >= ?",
            (session_id, msg_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[loop-detector] DB delete failed: {e}")
        return False
    finally:
        conn.close()


def perform_rollback(
    session_id: str,
    loop_start_index: int,
    ctx,
    recovery_prompt: str,
) -> bool:
    """セッションを巻き戻し、回復プロンプトを注入"""
    print(
        f"[loop-detector] Rolling back session {session_id} to index {loop_start_index}"
    )

    success = delete_messages_after(session_id, loop_start_index)
    if not success:
        print("[loop-detector] Failed to delete messages from DB")
        return False

    try:
        ctx.inject_message(recovery_prompt, role="user")
        print("[loop-detector] Injected recovery prompt")
        return True
    except Exception as e:
        print(f"[loop-detector] Failed to inject recovery prompt: {e}")
        return False
