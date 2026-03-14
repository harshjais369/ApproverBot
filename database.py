import sqlite3
import json
from typing import Optional, List
from config import DB_PATH

_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def init_db() -> None:
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pending_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
        );
        CREATE INDEX IF NOT EXISTS idx_pending_token ON pending_requests(token);
        CREATE INDEX IF NOT EXISTS idx_pending_user ON pending_requests(user_id, status);

        CREATE TABLE IF NOT EXISTS fingerprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_id TEXT,
            canvas_hash TEXT,
            webgl_hash TEXT,
            audio_hash TEXT,
            ip_address TEXT,
            screen_resolution TEXT,
            user_agent TEXT,
            platform TEXT,
            languages TEXT,
            timezone TEXT,
            timezone_offset INTEGER,
            touch_points INTEGER,
            device_memory REAL,
            hardware_concurrency INTEGER,
            fonts_hash TEXT,
            raw_data TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_fp_user ON fingerprints(user_id);
        CREATE INDEX IF NOT EXISTS idx_fp_device_id ON fingerprints(device_id);
        CREATE INDEX IF NOT EXISTS idx_fp_canvas ON fingerprints(canvas_hash);

        CREATE TABLE IF NOT EXISTS flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            new_user_id INTEGER NOT NULL,
            matched_user_id INTEGER NOT NULL,
            similarity_score REAL NOT NULL,
            matching_components TEXT NOT NULL,
            action_taken TEXT NOT NULL DEFAULT 'flagged',
            chat_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_flags_new ON flags(new_user_id);
        CREATE INDEX IF NOT EXISTS idx_flags_matched ON flags(matched_user_id);
    """)
    conn.commit()


# ── Pending Requests ──────────────────────────────────────────────

def create_pending_request(chat_id: int, user_id: int,
                           token: Optional[str] = None,
                           expires_at: Optional[str] = None,
                           status: str = "pending") -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO pending_requests (token, chat_id, user_id, expires_at, status) VALUES (?, ?, ?, ?, ?)",
        (token, chat_id, user_id, expires_at, status),
    )
    conn.commit()


def get_pending_request(token: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM pending_requests WHERE token = ? AND status = 'pending' AND (expires_at IS NULL OR expires_at > datetime('now'))",
        (token,),
    ).fetchone()
    return dict(row) if row else None


def get_restricted_requests(user_id: int) -> List[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM pending_requests WHERE user_id = ? AND status = 'restricted'",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_pending_token(request_id: int, token: str, expires_at: str) -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE pending_requests SET token = ?, expires_at = ?, status = 'pending' WHERE id = ?",
        (token, expires_at, request_id),
    )
    conn.commit()


def mark_pending_completed(token: str) -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE pending_requests SET status = 'completed' WHERE token = ?",
        (token,),
    )
    conn.commit()


def expire_stale_requests() -> int:
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE pending_requests SET status = 'expired' WHERE expires_at < datetime('now') AND status = 'pending'"
    )
    conn.commit()
    return cur.rowcount


# ── Fingerprints ──────────────────────────────────────────────────

def upsert_fingerprint(user_id: int, fp: dict) -> int:
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM fingerprints WHERE user_id = ?", (user_id,)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE fingerprints SET
                device_id=?, canvas_hash=?, webgl_hash=?, audio_hash=?,
                ip_address=?, screen_resolution=?, user_agent=?, platform=?,
                languages=?, timezone=?, timezone_offset=?, touch_points=?,
                device_memory=?, hardware_concurrency=?, fonts_hash=?,
                raw_data=?, updated_at=datetime('now')
            WHERE user_id=?
        """, (
            fp.get("device_id"), fp.get("canvas_hash"), fp.get("webgl_hash"),
            fp.get("audio_hash"), fp.get("ip_address"), fp.get("screen_resolution"),
            fp.get("user_agent"), fp.get("platform"), fp.get("languages"),
            fp.get("timezone"), fp.get("timezone_offset"), fp.get("touch_points"),
            fp.get("device_memory"), fp.get("hardware_concurrency"),
            fp.get("fonts_hash"), fp.get("raw_data"), user_id,
        ))
        conn.commit()
        return existing["id"]
    else:
        cur = conn.execute("""
            INSERT INTO fingerprints (
                user_id, device_id, canvas_hash, webgl_hash, audio_hash,
                ip_address, screen_resolution, user_agent, platform,
                languages, timezone, timezone_offset, touch_points,
                device_memory, hardware_concurrency, fonts_hash, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, fp.get("device_id"), fp.get("canvas_hash"),
            fp.get("webgl_hash"), fp.get("audio_hash"), fp.get("ip_address"),
            fp.get("screen_resolution"), fp.get("user_agent"), fp.get("platform"),
            fp.get("languages"), fp.get("timezone"), fp.get("timezone_offset"),
            fp.get("touch_points"), fp.get("device_memory"),
            fp.get("hardware_concurrency"), fp.get("fonts_hash"),
            fp.get("raw_data"),
        ))
        conn.commit()
        return cur.lastrowid


def get_all_fingerprints_except(user_id: int) -> List[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM fingerprints WHERE user_id != ?", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def find_by_device_id(device_id: str, exclude_user_id: int) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM fingerprints WHERE device_id = ? AND user_id != ?",
        (device_id, exclude_user_id),
    ).fetchone()
    return dict(row) if row else None


# ── Flags ─────────────────────────────────────────────────────────

def record_flag(new_user_id: int, matched_user_id: int, score: float,
                matching_components: list, action: str, chat_id: int) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO flags (new_user_id, matched_user_id, similarity_score, matching_components, action_taken, chat_id) VALUES (?, ?, ?, ?, ?, ?)",
        (new_user_id, matched_user_id, score, json.dumps(matching_components), action, chat_id),
    )
    conn.commit()
    return cur.lastrowid


def get_flags_for_user(user_id: int) -> List[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM flags WHERE new_user_id = ? OR matched_user_id = ?",
        (user_id, user_id),
    ).fetchall()
    return [dict(r) for r in rows]
