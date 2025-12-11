#!/usr/bin/env python3
"""Test SQLite database connection and basic schema presence"""

import sqlite3
import sys
import os

DB_NAME = "myapp.db"

def table_exists(cursor, name: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cursor.fetchone() is not None

try:
    # Check if database file exists
    if not os.path.exists(DB_NAME):
        print(f"Database file '{DB_NAME}' not found")
        sys.exit(1)
    
    # Connect to database and get version
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("SELECT sqlite_version()")
    version = cursor.fetchone()[0]

    # Verify tables exist
    required_tables = [
        "app_info", "users", "videos", "tags", "video_tags", "watch_history", "refresh_tokens"
    ]
    missing = [t for t in required_tables if not table_exists(cursor, t)]
    if missing:
        print(f"Schema missing tables: {', '.join(missing)}")
        conn.close()
        sys.exit(1)

    # Simple sanity checks for seeds (not strict)
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM videos")
    video_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tags")
    tags_count = cursor.fetchone()[0]

    conn.close()
    
    print(f"SQLite version: {version}")
    print(f"Tables OK. Users: {user_count}, Videos: {video_count}, Tags: {tags_count}")
    sys.exit(0)
    
except sqlite3.Error as e:
    print(f"Connection failed: {e}")
    sys.exit(1)
