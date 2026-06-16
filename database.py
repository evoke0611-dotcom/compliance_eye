import datetime
import hashlib
import json
import secrets
import sqlite3

from project_paths import DB_PATH


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def init_db():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT NOT NULL UNIQUE,
            organization TEXT,
            employee_name TEXT,
            date TEXT NOT NULL,
            final_report TEXT,
            basic_info_json TEXT,
            chat_log_json TEXT,
            messages_json TEXT,
            state_json TEXT,
            is_complete INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    cols = {row["name"] for row in cur.execute("PRAGMA table_info(audit_sessions)").fetchall()}
    if "state_json" not in cols:
        cur.execute("ALTER TABLE audit_sessions ADD COLUMN state_json TEXT")
    conn.commit()
    conn.close()


def register_user(username: str, email: str, full_name: str, password: str) -> dict:
    salt = secrets.token_hex(16)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, email, full_name, salt, password_hash, created_at) VALUES (?,?,?,?,?,?)",
            (
                username.strip().lower(),
                email.strip().lower(),
                full_name.strip(),
                salt,
                _hash_password(password, salt),
                now,
            ),
        )
        conn.commit()
        return {"success": True, "message": "Account created successfully."}
    except sqlite3.IntegrityError as exc:
        message = str(exc).lower()
        if "username" in message:
            return {"success": False, "message": "Username already exists."}
        if "email" in message:
            return {"success": False, "message": "Email is already registered."}
        return {"success": False, "message": "Registration failed."}
    finally:
        conn.close()


def login_user(username: str, password: str) -> dict:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
        if not row:
            return {"success": False, "user": None, "message": "Username not found."}
        if _hash_password(password, row["salt"]) != row["password_hash"]:
            return {"success": False, "user": None, "message": "Incorrect password."}
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, row["id"]))
        conn.commit()
        return {"success": True, "user": dict(row), "message": "Login successful."}
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_audit_session(
    user_id: int,
    basic_info: dict,
    chat_log: list,
    messages: list,
    final_report: str = "",
    is_complete: bool = False,
    state: dict | None = None,
) -> str:
    token = secrets.token_hex(12)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO audit_sessions
            (user_id, session_token, organization, employee_name, date,
             final_report, basic_info_json, chat_log_json, messages_json, state_json, is_complete)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            user_id,
            token,
            basic_info.get("org_name", "Unknown"),
            basic_info.get("emp_name", "Unknown"),
            now,
            final_report,
            json.dumps(basic_info, ensure_ascii=False),
            json.dumps(chat_log, ensure_ascii=False),
            json.dumps(messages, ensure_ascii=False),
            json.dumps(state or {}, ensure_ascii=False),
            1 if is_complete else 0,
        ),
    )
    conn.commit()
    conn.close()
    return token


def update_audit_session(
    session_token: str,
    chat_log: list,
    messages: list,
    final_report: str = "",
    is_complete: bool = False,
    state: dict | None = None,
):
    conn = _get_conn()
    conn.execute(
        """
        UPDATE audit_sessions
        SET chat_log_json = ?, messages_json = ?, final_report = ?, state_json = ?, is_complete = ?
        WHERE session_token = ?
        """,
        (
            json.dumps(chat_log, ensure_ascii=False),
            json.dumps(messages, ensure_ascii=False),
            final_report,
            json.dumps(state or {}, ensure_ascii=False),
            1 if is_complete else 0,
            session_token,
        ),
    )
    conn.commit()
    conn.close()


def get_user_audit_history(user_id: int) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM audit_sessions WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        item["basic_info"] = json.loads(item.pop("basic_info_json", "{}") or "{}")
        item["chat_log"] = json.loads(item.pop("chat_log_json", "[]") or "[]")
        item["messages"] = json.loads(item.pop("messages_json", "[]") or "[]")
        item["state"] = json.loads(item.pop("state_json", "{}") or "{}")
        result.append(item)
    return result


def delete_audit_session(session_token: str, user_id: int):
    conn = _get_conn()
    conn.execute(
        "DELETE FROM audit_sessions WHERE session_token = ? AND user_id = ?",
        (session_token, user_id),
    )
    conn.commit()
    conn.close()
