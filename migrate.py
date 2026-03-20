#!/usr/bin/env python3
"""
Database Migration & IP Geolocation Batch Update Script
========================================================

This script handles:
1. All database migrations (schema creation/updates)
2. Batch IP geolocation backfill via ip-api.com batch endpoint
3. Migration status tracking and logging

Usage:
    python migrate.py                          # Run all migrations
    python migrate.py --backfill              # Run migrations + batch backfill
    python migrate.py --backfill-only         # Only backfill without migrations
"""

import sqlite3
import json
import logging
import argparse
import requests
import time
from typing import Optional, List, Dict
from datetime import datetime
from config import DB_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Handles all database schema migrations."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = None

    def connect(self) -> sqlite3.Connection:
        """Establish database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            logger.info(f"Connected to database: {self.db_path}")
        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")

    def run_all_migrations(self) -> bool:
        """Run all database migrations in order."""
        try:
            conn = self.connect()

            # Migration 1: Create pending_requests table
            logger.info("Migration 1: Creating pending_requests table...")
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
            """)
            conn.commit()
            logger.info("✓ pending_requests table created/verified")

            # Migration 2: Create fingerprints table
            logger.info("Migration 2: Creating fingerprints table...")
            conn.executescript("""
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
            """)
            conn.commit()
            logger.info("✓ fingerprints table created/verified")

            # Migration 3: Create flags table
            logger.info("Migration 3: Creating flags table...")
            conn.executescript("""
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
            logger.info("✓ flags table created/verified")

            # Migration 4: Add ip_info column to fingerprints (NEW)
            logger.info("Migration 4: Adding ip_info column to fingerprints...")
            try:
                conn.execute("ALTER TABLE fingerprints ADD COLUMN ip_info TEXT")
                conn.commit()
                logger.info("✓ ip_info column added to fingerprints")
            except sqlite3.OperationalError:
                logger.info("✓ ip_info column already exists")

            # Migration 5: Reorder ip_info column to proper position (after raw_data)
            logger.info("Migration 5: Reordering columns (ip_info should be after raw_data)...")
            if self._needs_column_reorder(conn):
                self._reorder_fingerprints_columns(conn)
                logger.info("✓ Columns reordered successfully")
            else:
                logger.info("✓ Columns already in correct order")

            logger.info("\n✓✓✓ All migrations completed successfully! ✓✓✓\n")
            return True

        except sqlite3.Error as e:
            logger.error(f"Database migration failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during migration: {e}")
            return False

    def _get_column_position(self, conn, table: str, column: str) -> int:
        """Get the 0-indexed position of a column in a table. Returns -1 if not found."""
        cursor = conn.execute(f"PRAGMA table_info({table})")
        for idx, row in enumerate(cursor):
            if row[1] == column:  # row[1] is column name
                return idx
        return -1

    def _needs_column_reorder(self, conn) -> bool:
        """Check if ip_info is not immediately after raw_data (needs reordering)."""
        raw_data_pos = self._get_column_position(conn, "fingerprints", "raw_data")
        ip_info_pos = self._get_column_position(conn, "fingerprints", "ip_info")

        if raw_data_pos == -1 or ip_info_pos == -1:
            return False  # One or both columns don't exist, skip reordering

        # ip_info should be at position raw_data_pos + 1
        return ip_info_pos != raw_data_pos + 1

    def _reorder_fingerprints_columns(self, conn):
        """Rebuild fingerprints table with correct column order."""
        try:
            conn.execute("BEGIN TRANSACTION")

            # Create new table with correct column order
            conn.execute("""
                CREATE TABLE fingerprints_reordered (
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
                )
            """)

            # Copy data from old table to new table with correct column order
            conn.execute("""
                INSERT INTO fingerprints_reordered
                (id, user_id, full_name, device_id, canvas_hash, webgl_hash, audio_hash,
                 ip_address, screen_resolution, user_agent, platform, languages, timezone,
                 timezone_offset, touch_points, device_memory, hardware_concurrency,
                 fonts_hash, raw_data, ip_info, created_at, updated_at)
                SELECT
                id, user_id, full_name, device_id, canvas_hash, webgl_hash, audio_hash,
                ip_address, screen_resolution, user_agent, platform, languages, timezone,
                timezone_offset, touch_points, device_memory, hardware_concurrency,
                fonts_hash, raw_data, ip_info, created_at, updated_at
                FROM fingerprints
            """)

            # Drop old table and rename new one
            conn.execute("DROP TABLE fingerprints")
            conn.execute("ALTER TABLE fingerprints_reordered RENAME TO fingerprints")

            # Recreate indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fp_user ON fingerprints(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fp_device_id ON fingerprints(device_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fp_canvas ON fingerprints(canvas_hash)")

            conn.execute("COMMIT")
            logger.info("  [OK] Column reordering completed successfully")
        except sqlite3.Error as e:
            conn.execute("ROLLBACK")
            logger.error(f"  [ERROR] Failed to reorder columns: {e}")
            raise

    def get_fingerprints_without_ip_info(self) -> List[Dict]:
        """Get all fingerprints with ip_address but missing ip_info."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT id, user_id, ip_address FROM fingerprints "
            "WHERE ip_address IS NOT NULL AND ip_address != '' AND ip_info IS NULL "
            "ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_ip_info(self, fingerprint_id: int, ip_info: Dict) -> bool:
        """Update ip_info for a specific fingerprint."""
        try:
            conn = self.connect()
            conn.execute(
                "UPDATE fingerprints SET ip_info = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(ip_info) if ip_info else None, fingerprint_id)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update ip_info for fingerprint {fingerprint_id}: {e}")
            return False


class IPGeolocationBatchUpdater:
    """Handles batch IP geolocation lookups via ip-api.com batch API."""

    BATCH_API_URL = "http://ip-api.com/batch"
    BATCH_SIZE = 100  # Max 100 per request
    RATE_LIMIT_DELAY = 4.1  # 15 requests per minute = ~4 seconds between batches
    TIMEOUT = 10

    def __init__(self, db_path: str = DB_PATH):
        self.db = DatabaseMigrator(db_path)
        self.stats = {
            "total": 0,
            "processed": 0,
            "updated": 0,
            "failed": 0,
            "skipped": 0,
        }

    def backfill_ip_geolocation(self) -> bool:
        """
        Fetch IP geolocation for all fingerprints missing ip_info.
        Uses batch API for efficiency (up to 100 IPs per request).
        """
        try:
            fingerprints = self.db.get_fingerprints_without_ip_info()
            self.stats["total"] = len(fingerprints)

            if self.stats["total"] == 0:
                logger.info("No fingerprints to backfill - all have ip_info!")
                return True

            logger.info(f"\nStarting IP geolocation backfill for {self.stats['total']} fingerprints...")
            logger.info(f"Using batch API: {self.BATCH_API_URL}")
            logger.info(f"Rate limit: {self.RATE_LIMIT_DELAY}s between batches\n")

            # Process in batches
            for i in range(0, self.stats["total"], self.BATCH_SIZE):
                batch = fingerprints[i:i + self.BATCH_SIZE]
                logger.info(f"Processing batch {(i // self.BATCH_SIZE) + 1} "
                           f"({len(batch)} IPs, offset {i}/{self.stats['total']})...")

                if self._process_batch(batch):
                    self.stats["processed"] += len(batch)

                # Rate limiting between batches
                if i + self.BATCH_SIZE < self.stats["total"]:
                    logger.info(f"Rate limit: waiting {self.RATE_LIMIT_DELAY}s before next batch...")
                    time.sleep(self.RATE_LIMIT_DELAY)

            # Print summary
            self._print_summary()
            return self.stats["failed"] == 0

        except Exception as e:
            logger.error(f"Batch update failed: {e}")
            return False

    def _process_batch(self, batch: List[Dict]) -> bool:
        """Process a single batch of IP addresses."""
        try:
            # Build request payload
            query_list = [{"query": fp["ip_address"]} for fp in batch]

            # Call batch API
            response = requests.post(
                self.BATCH_API_URL,
                json=query_list,
                timeout=self.TIMEOUT,
                params={"fields": "status,isp,city,regionName,country,mobile"}
            )
            response.raise_for_status()

            results = response.json()

            # Process results and update database
            for fp, result in zip(batch, results):
                if result.get("status") == "success":
                    ip_info = {
                        "isp": result.get("isp", "").strip(),
                        "location": ", ".join(
                            p for p in [
                                result.get("city", "").strip(),
                                result.get("regionName", "").strip(),
                                result.get("country", "").strip(),
                            ] if p
                        ),
                        "mobile": bool(result.get("mobile", False))
                    }

                    if self.db.update_ip_info(fp["id"], ip_info):
                        self.stats["updated"] += 1
                        logger.debug(
                            f"  ✓ {fp['ip_address']} → {ip_info['location']}"
                        )
                    else:
                        self.stats["failed"] += 1
                else:
                    self.stats["skipped"] += 1
                    logger.warning(
                        f"  ○ {fp['ip_address']} → API error: {result.get('message', 'unknown')}"
                    )

            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"  ✗ API request failed: {e}")
            self.stats["failed"] += len(batch)
            return False
        except json.JSONDecodeError as e:
            logger.error(f"  ✗ Failed to parse API response: {e}")
            self.stats["failed"] += len(batch)
            return False
        except Exception as e:
            logger.error(f"  ✗ Unexpected error processing batch: {e}")
            self.stats["failed"] += len(batch)
            return False

    def _print_summary(self):
        """Print summary statistics."""
        logger.info("\n" + "="*60)
        logger.info("BACKFILL SUMMARY")
        logger.info("="*60)
        logger.info(f"Total fingerprints: {self.stats['total']}")
        logger.info(f"Processed: {self.stats['processed']}")
        logger.info(f"Updated: {self.stats['updated']} ✓")
        logger.info(f"Skipped: {self.stats['skipped']} ○")
        logger.info(f"Failed: {self.stats['failed']} ✗")
        logger.info("="*60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database migration and IP geolocation batch update",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate.py                    # Run migrations only
  python migrate.py --backfill        # Migrations + batch backfill
  python migrate.py --backfill-only   # Backfill without migration
        """
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Run migrations and batch backfill IP geolocation data"
    )
    parser.add_argument(
        "--backfill-only",
        action="store_true",
        help="Only backfill IP geolocation data (skip migrations)"
    )
    parser.add_argument(
        "--db-path",
        default=DB_PATH,
        help=f"Path to database file (default: {DB_PATH})"
    )

    args = parser.parse_args()

    logger.info("\n" + "="*60)
    logger.info("DATABASE MIGRATION & IP GEOLOCATION BACKFILL")
    logger.info("="*60 + "\n")

    # Step 1: Run migrations (unless --backfill-only)
    if not args.backfill_only:
        migrator = DatabaseMigrator(args.db_path)
        if not migrator.run_all_migrations():
            logger.error("Migrations failed!")
            return 1
        migrator.close()

    # Step 2: Backfill IP geolocation (if requested)
    if args.backfill or args.backfill_only:
        logger.info("")
        updater = IPGeolocationBatchUpdater(args.db_path)
        if not updater.backfill_ip_geolocation():
            logger.warning("Backfill completed with errors")
            return 1

    logger.info("All done!")
    return 0


if __name__ == "__main__":
    exit(main())
