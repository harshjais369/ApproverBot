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
            status TEXT NOT NULL DEFAULT 'pending',
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_name TEXT,
            token TEXT UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pending_token ON pending_requests(token);
        CREATE INDEX IF NOT EXISTS idx_pending_user ON pending_requests(user_id, status);

        CREATE TABLE IF NOT EXISTS fingerprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            full_name TEXT,
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
            ip_info TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_fp_user ON fingerprints(user_id);
        CREATE INDEX IF NOT EXISTS idx_fp_device_id ON fingerprints(device_id);
        CREATE INDEX IF NOT EXISTS idx_fp_canvas ON fingerprints(canvas_hash);

        CREATE TABLE IF NOT EXISTS flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            new_user_id INTEGER NOT NULL,
            new_user_name TEXT,
            matched_user_id INTEGER NOT NULL,
            matched_user_name TEXT,
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

    # TODO: Remove migration code after it has been deployed once
    # Add ip_info column to fingerprints if it doesn't exist (migration for existing DBs)
    try:
        conn.execute("ALTER TABLE fingerprints ADD COLUMN ip_info TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass


# ── Pending Requests ──────────────────────────────────────────────

def create_pending_request(chat_id: int, user_id: int, user_name: str = None,
                           token: Optional[str] = None,
                           expires_at: Optional[str] = None,
                           status: str = "pending") -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO pending_requests (token, chat_id, user_id, user_name, expires_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        (token, chat_id, user_id, user_name, expires_at, status),
    )
    conn.commit()


def get_pending_request(token: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM pending_requests WHERE token = ? AND status = 'pending' AND (expires_at IS NULL OR expires_at > datetime('now'))",
        (token,),
    ).fetchone()
    return dict(row) if row else None


def get_active_pending_request(chat_id: int, user_id: int) -> Optional[dict]:
    """Return latest non-expired pending request for a specific chat/user."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM pending_requests "
        "WHERE chat_id = ? AND user_id = ? AND status = 'pending' "
        "AND (expires_at IS NULL OR expires_at > datetime('now')) "
        "ORDER BY id DESC LIMIT 1",
        (chat_id, user_id),
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
                full_name=?, device_id=?, canvas_hash=?, webgl_hash=?, audio_hash=?,
                ip_address=?, screen_resolution=?, user_agent=?, platform=?,
                languages=?, timezone=?, timezone_offset=?, touch_points=?,
                device_memory=?, hardware_concurrency=?, fonts_hash=?,
                raw_data=?, ip_info=?, updated_at=datetime('now')
            WHERE user_id=?
        """, (
            fp.get("full_name"), fp.get("device_id"), fp.get("canvas_hash"),
            fp.get("webgl_hash"), fp.get("audio_hash"), fp.get("ip_address"),
            fp.get("screen_resolution"), fp.get("user_agent"), fp.get("platform"),
            fp.get("languages"), fp.get("timezone"), fp.get("timezone_offset"),
            fp.get("touch_points"), fp.get("device_memory"),
            fp.get("hardware_concurrency"), fp.get("fonts_hash"),
            fp.get("raw_data"), fp.get("ip_info"), user_id,
        ))
        conn.commit()
        return existing["id"]
    else:
        cur = conn.execute("""
            INSERT INTO fingerprints (
                user_id, full_name, device_id, canvas_hash, webgl_hash, audio_hash,
                ip_address, screen_resolution, user_agent, platform,
                languages, timezone, timezone_offset, touch_points,
                device_memory, hardware_concurrency, fonts_hash, raw_data, ip_info
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, fp.get("full_name"), fp.get("device_id"), fp.get("canvas_hash"),
            fp.get("webgl_hash"), fp.get("audio_hash"), fp.get("ip_address"),
            fp.get("screen_resolution"), fp.get("user_agent"), fp.get("platform"),
            fp.get("languages"), fp.get("timezone"), fp.get("timezone_offset"),
            fp.get("touch_points"), fp.get("device_memory"),
            fp.get("hardware_concurrency"), fp.get("fonts_hash"),
            fp.get("raw_data"), fp.get("ip_info"),
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


def find_by_ip(ip_address: str, exclude_user_id: int) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM fingerprints WHERE ip_address = ? AND user_id != ?",
        (ip_address, exclude_user_id),
    ).fetchone()
    return dict(row) if row else None


def get_user_name(user_id: int) -> Optional[str]:
    """Look up the stored full_name for a user from their fingerprint record."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT full_name FROM fingerprints WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row["full_name"] if row and row["full_name"] else None


# ── Flags ─────────────────────────────────────────────────────────

def record_flag(new_user_id: int, matched_user_id: int, score: float,
                matching_components: list, action: str, chat_id: int,
                new_user_name: str = None, matched_user_name: str = None) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO flags (new_user_id, new_user_name, matched_user_id, matched_user_name, similarity_score, matching_components, action_taken, chat_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (new_user_id, new_user_name, matched_user_id, matched_user_name, score, json.dumps(matching_components), action, chat_id),
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


def mark_false_positive(new_user_id: int, matched_user_id: int) -> None:
    """Mark a flag as false positive. Does NOT delete any data."""
    conn = _get_conn()
    conn.execute(
        "UPDATE flags SET action_taken = 'false_positive' "
        "WHERE new_user_id = ? AND matched_user_id = ? AND action_taken != 'false_positive'",
        (new_user_id, matched_user_id),
    )
    conn.commit()


def find_existing_link(user_id: int) -> Optional[dict]:
    """
    Check if this user is already linked to another user (from past flags).
    Excludes false_positive flags. Returns the first linked user's flag or None.
    """
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM flags WHERE (new_user_id = ? OR matched_user_id = ?) "
        "AND action_taken != 'false_positive' LIMIT 1",
        (user_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def get_all_connected_users(user_id: int) -> set:
    """
    Find all user_ids transitively connected to user_id through the flags table.
    If A↔B and B↔C, then get_all_connected_users(A) returns {A, B, C}.
    Excludes false_positive flags.
    """
    conn = _get_conn()
    visited = set()
    queue = [user_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        rows = conn.execute(
            "SELECT new_user_id, matched_user_id FROM flags "
            "WHERE (new_user_id = ? OR matched_user_id = ?) "
            "AND action_taken != 'false_positive'",
            (current, current),
        ).fetchall()

        for row in rows:
            for uid in [row["new_user_id"], row["matched_user_id"]]:
                if uid not in visited:
                    queue.append(uid)

    return visited


def get_all_multi_account_clusters() -> list:
    """
    Find all clusters of linked users (connected components in the flags graph).
    Returns list of sets, each set containing user_ids that are linked.
    Excludes false_positive flags.
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT DISTINCT new_user_id, matched_user_id FROM flags "
        "WHERE action_taken != 'false_positive'"
    ).fetchall()

    # Build adjacency from all flag pairs
    all_users = set()
    for row in rows:
        all_users.add(row["new_user_id"])
        all_users.add(row["matched_user_id"])

    # BFS to find connected components
    visited = set()
    clusters = []

    for uid in all_users:
        if uid in visited:
            continue
        cluster = get_all_connected_users(uid)
        visited.update(cluster)
        if len(cluster) > 1:
            clusters.append(cluster)

    return clusters


def get_connection_details(user_id: int) -> List[dict]:
    """
    Get all flag records involving any user in the connected component of user_id.
    """
    connected = get_all_connected_users(user_id)
    if len(connected) <= 1:
        return []

    conn = _get_conn()
    placeholders = ",".join("?" for _ in connected)
    rows = conn.execute(
        f"SELECT * FROM flags WHERE new_user_id IN ({placeholders}) "
        f"OR matched_user_id IN ({placeholders})",
        list(connected) + list(connected),
    ).fetchall()
    return [dict(r) for r in rows]
