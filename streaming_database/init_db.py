#!/usr/bin/env python3
"""Initialize SQLite database for streaming_database with idempotent schema and seed data.

Tables:
- app_info: basic metadata
- users: auth users with username, email, password_hash
- videos: video metadata and file_path (points to backend media directory)
- tags: catalog tags
- video_tags: M2M relation between videos and tags
- watch_history: per-user video progress/history
- refresh_tokens (optional): for session refreshes

All CREATE statements use IF NOT EXISTS and are executed separately.
All seed inserts use INSERT OR IGNORE to remain idempotent.

This script also writes db_connection.txt and updates db_visualizer/sqlite.env.
"""

import sqlite3
import os
from datetime import datetime

DB_NAME = "myapp.db"
DB_USER = "kaviasqlite"  # Not used for SQLite, retained for parity
DB_PASSWORD = "kaviadefaultpassword"  # Not used for SQLite
DB_PORT = "5000"  # Not used for SQLite

print("Starting SQLite setup...")

# Ensure database presence
db_exists = os.path.exists(DB_NAME)
if db_exists:
    print(f"SQLite database already exists at {DB_NAME}")
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.execute("SELECT 1")
        conn.close()
        print("Database is accessible and working.")
    except Exception as e:
        print(f"Warning: Database exists but may be corrupted: {e}")
else:
    print("Creating new SQLite database...")

# Connect and create schema
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Enable foreign keys
cursor.execute("PRAGMA foreign_keys = ON")

# app_info
cursor.execute(
    "CREATE TABLE IF NOT EXISTS app_info ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " key TEXT UNIQUE NOT NULL,"
    " value TEXT,"
    " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
)

# users with auth fields
cursor.execute(
    "CREATE TABLE IF NOT EXISTS users ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " username TEXT UNIQUE NOT NULL,"
    " email TEXT UNIQUE NOT NULL,"
    " password_hash TEXT NOT NULL,"
    " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
)

# videos
cursor.execute(
    "CREATE TABLE IF NOT EXISTS videos ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " title TEXT NOT NULL,"
    " description TEXT DEFAULT '',"
    " file_path TEXT NOT NULL,"
    " duration_seconds INTEGER DEFAULT 0,"
    " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
)

# tags
cursor.execute(
    "CREATE TABLE IF NOT EXISTS tags ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " name TEXT UNIQUE NOT NULL)"
)

# video_tags junction
cursor.execute(
    "CREATE TABLE IF NOT EXISTS video_tags ("
    " video_id INTEGER NOT NULL,"
    " tag_id INTEGER NOT NULL,"
    " PRIMARY KEY (video_id, tag_id),"
    " FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,"
    " FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE)"
)

# watch_history
cursor.execute(
    "CREATE TABLE IF NOT EXISTS watch_history ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " user_id INTEGER NOT NULL,"
    " video_id INTEGER NOT NULL,"
    " last_watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
    " position_seconds INTEGER DEFAULT 0,"
    " completed INTEGER DEFAULT 0,"
    " UNIQUE(user_id, video_id),"
    " FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,"
    " FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE)"
)

# optional refresh_tokens
cursor.execute(
    "CREATE TABLE IF NOT EXISTS refresh_tokens ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " user_id INTEGER NOT NULL,"
    " token TEXT UNIQUE NOT NULL,"
    " expires_at TIMESTAMP NOT NULL,"
    " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
    " FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)"
)

# Seed app_info (idempotent using INSERT OR REPLACE for fixed keys)
cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)", ("project_name", "streaming_database"))
cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)", ("version", "0.2.0"))
cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)", ("author", "StreamFlix Team"))
cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)", ("description", "Streaming database schema and seed"))

# Seed users (bcrypt hashes produced externally; stored here as string)
# Example hashes for 'password123' (do not rely on these for production)
# Determine correct password column name based on existing schema (avoid destructive changes)
password_col = "password_hash"
try:
    cursor.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in cursor.fetchall()]
    if "password_hash" not in cols and "password" in cols:
        password_col = "password"
except Exception:
    # Fallback silently to default 'password_hash'
    pass

users_seed = [
    ("alice", "alice@example.com", "$2b$12$C1i4b5lH2qH5I2nCq0fS7u4xw3CwNq6m5x1g8mOa0J3iJ6s5M3m9G"),
    ("bob", "bob@example.com", "$2b$12$C1i4b5lH2qH5I2nCq0fS7u4xw3CwNq6m5x1g8mOa0J3iJ6s5M3m9G"),
]
for username, email, ph in users_seed:
    cursor.execute(
        f"INSERT OR IGNORE INTO users (username, email, {password_col}) VALUES (?, ?, ?)",
        (username, email, ph),
    )

# Resolve backend media dir file paths (placeholder paths for now)
backend_media_root = os.path.abspath(os.path.join("..", "streaming_backend", "media"))
# Use generic sample files pointing to backend media directory
videos_seed = [
    ("The Ocean Journey", "A calming exploration of the deep blue.", os.path.join(backend_media_root, "ocean.mp4"), 600),
    ("City Timelapse", "A fast-paced timelapse of a bustling city.", os.path.join(backend_media_root, "city.mp4"), 300),
    ("Mountain Hike", "A scenic hike through mountainous terrain.", os.path.join(backend_media_root, "mountain.mp4"), 900),
]
for title, desc, fpath, dur in videos_seed:
    cursor.execute(
        "INSERT OR IGNORE INTO videos (title, description, file_path, duration_seconds) VALUES (?, ?, ?, ?)",
        (title, desc, fpath, dur),
    )

# Seed tags
tags_seed = ["Nature", "Travel", "City", "Relaxing", "Documentary"]
for t in tags_seed:
    cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (t,))

# Build a small mapping for video_tags (idempotent)
# Fetch ids
cursor.execute("SELECT id, title FROM videos")
video_rows = cursor.fetchall()
cursor.execute("SELECT id, name FROM tags")
tag_rows = cursor.fetchall()
title_to_id = {t: i for (i, t) in video_rows}
name_to_id = {n: i for (i, n) in tag_rows}

relations = [
    ("The Ocean Journey", ["Nature", "Relaxing", "Documentary"]),
    ("City Timelapse", ["City", "Travel"]),
    ("Mountain Hike", ["Nature", "Travel", "Documentary"]),
]

for vtitle, tag_names in relations:
    vid = title_to_id.get(vtitle)
    if not vid:
        continue
    for tname in tag_names:
        tid = name_to_id.get(tname)
        if not tid:
            continue
        cursor.execute(
            "INSERT OR IGNORE INTO video_tags (video_id, tag_id) VALUES (?, ?)",
            (vid, tid),
        )

# Seed sample watch history (idempotent)
# Map usernames to ids
cursor.execute("SELECT id, username FROM users")
user_rows = cursor.fetchall()
uname_to_id = {u: i for (i, u) in user_rows}

# Create simple history entries
history_seed = [
    ("alice", "The Ocean Journey", 120, 0),
    ("alice", "City Timelapse", 300, 1),
    ("bob", "Mountain Hike", 240, 0),
]
for uname, vtitle, pos, completed in history_seed:
    uid = uname_to_id.get(uname)
    vid = title_to_id.get(vtitle)
    if uid and vid:
        # Use INSERT OR IGNORE with UNIQUE(user_id, video_id)
        cursor.execute(
            "INSERT OR IGNORE INTO watch_history (user_id, video_id, position_seconds, completed, last_watched_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, vid, pos, completed, datetime.utcnow().isoformat()),
        )

conn.commit()

# Stats
cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
table_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM app_info")
record_count = cursor.fetchone()[0]

conn.close()

# Save connection info
current_dir = os.getcwd()
connection_string = f"sqlite:///{current_dir}/{DB_NAME}"
try:
    with open("db_connection.txt", "w") as f:
        f.write(f"# SQLite connection methods:\n")
        f.write(f"# Python: sqlite3.connect('{DB_NAME}')\n")
        f.write(f"# Connection string: {connection_string}\n")
        f.write(f"# File path: {current_dir}/{DB_NAME}\n")
    print("Connection information saved to db_connection.txt")
except Exception as e:
    print(f"Warning: Could not save connection info: {e}")

# Update db_visualizer env
db_path = os.path.abspath(DB_NAME)
if not os.path.exists("db_visualizer"):
    os.makedirs("db_visualizer", exist_ok=True)
    print("Created db_visualizer directory")

try:
    with open("db_visualizer/sqlite.env", "w") as f:
        f.write(f"export SQLITE_DB=\"{db_path}\"\n")
    print("Environment variables saved to db_visualizer/sqlite.env")
except Exception as e:
    print(f"Warning: Could not save environment variables: {e}")

print("\nSQLite setup complete!")
print(f"Database: {DB_NAME}")
print(f"Location: {current_dir}/{DB_NAME}")
print("")
print("To use with Node.js viewer, run: source db_visualizer/sqlite.env")
print("\nTo connect to the database, use one of the following methods:")
print(f"1. Python: sqlite3.connect('{DB_NAME}')")
print(f"2. Connection string: {connection_string}")
print(f"3. Direct file access: {current_dir}/{DB_NAME}")
print("")
print("Database statistics:")
print(f"  Tables: {table_count}")
print(f"  App info records: {record_count}")

# If sqlite3 CLI is available, show how to use it
try:
    import subprocess
    result = subprocess.run(['which', 'sqlite3'], capture_output=True, text=True)
    if result.returncode == 0:
        print("")
        print("SQLite CLI is available. You can also use:")
        print(f"  sqlite3 {DB_NAME}")
except Exception:
    pass

print("\nScript completed successfully.")
