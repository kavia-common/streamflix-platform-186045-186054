#!/usr/bin/env python3
"""
StreamFlix SQLite initialization script.

Creates the database schema (users, videos, watch_history) and idempotently seeds
initial data (users + videos).

Deterministic DB location:
- Default: <this_repo>/streaming_database/data/streamflix.sqlite3
- Override via env var: STREAMFLIX_SQLITE_PATH

This script is safe to run multiple times; it uses UNIQUE constraints and UPSERTs.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DbPaths:
    """Resolved paths for the DB file and seed data."""

    db_path: Path
    seed_videos_path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_paths() -> DbPaths:
    base_dir = Path(__file__).resolve().parent
    default_db_path = base_dir / "data" / "streamflix.sqlite3"
    db_path = Path(os.environ.get("STREAMFLIX_SQLITE_PATH", str(default_db_path))).expanduser().resolve()

    seed_videos_path = base_dir / "seed" / "seed_videos.json"
    return DbPaths(db_path=db_path, seed_videos_path=seed_videos_path)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Enforce foreign key constraints in SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    # Users: keep minimal fields needed for auth + uniqueness.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY,
            email           TEXT NOT NULL UNIQUE,
            username        TEXT NOT NULL UNIQUE,
            password_hash   TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
        """
    )

    # Videos: metadata table.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id                INTEGER PRIMARY KEY,
            slug              TEXT NOT NULL UNIQUE,
            title             TEXT NOT NULL,
            description       TEXT NOT NULL DEFAULT '',
            genre             TEXT NOT NULL DEFAULT '',
            release_year      INTEGER,
            duration_seconds  INTEGER,
            rating            REAL,
            tags_json         TEXT NOT NULL DEFAULT '[]',
            thumbnail_url     TEXT NOT NULL DEFAULT '',
            video_path        TEXT NOT NULL DEFAULT '',
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );
        """
    )

    # Watch history: one row per (user, video). Upsertable.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watch_history (
            id                INTEGER PRIMARY KEY,
            user_id           INTEGER NOT NULL,
            video_id          INTEGER NOT NULL,
            progress_seconds  INTEGER NOT NULL DEFAULT 0,
            completed         INTEGER NOT NULL DEFAULT 0,
            last_watched_at   TEXT NOT NULL,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL,
            UNIQUE(user_id, video_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
        );
        """
    )

    # Helpful indexes for backend queries.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_genre ON videos(genre);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_year ON videos(release_year);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_watch_history_user ON watch_history(user_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_watch_history_video ON watch_history(video_id);")


def _load_seed_videos(seed_path: Path) -> list[dict[str, Any]]:
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_path}")

    data = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("seed_videos.json must contain a JSON array of video objects")

    # Minimal validation to catch typos early.
    required = {"id", "slug", "title"}
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"seed_videos.json item #{i} must be an object")
        missing = required - set(item.keys())
        if missing:
            raise ValueError(f"seed_videos.json item #{i} missing required keys: {sorted(missing)}")

    return data


def _seed_users(conn: sqlite3.Connection) -> None:
    # NOTE: This is demo seed data. In production, do not ship fixed users/hashes.
    now = _utc_now_iso()

    # A known-valid bcrypt hash (ident 2b, cost 12) for password: "password"
    # (generated via passlib example). Backend auth can verify this.
    demo_password_hash = "$2b$12$NT0I31Sa7ihGEWpka9ASYrEFkhuTNeBQ2xfZskIiiJeyFXhRgS.Sy"

    users = [
        {
            "id": 1,
            "email": "demo@streamflix.local",
            "username": "demo",
            "password_hash": demo_password_hash,
        }
    ]

    for u in users:
        conn.execute(
            """
            INSERT INTO users (id, email, username, password_hash, created_at, updated_at)
            VALUES (:id, :email, :username, :password_hash, :created_at, :updated_at)
            ON CONFLICT(email) DO UPDATE SET
                username = excluded.username,
                password_hash = excluded.password_hash,
                updated_at = excluded.updated_at
            ;
            """,
            {
                **u,
                "created_at": now,
                "updated_at": now,
            },
        )


def _seed_videos(conn: sqlite3.Connection, seed_videos: list[dict[str, Any]]) -> None:
    now = _utc_now_iso()

    for v in seed_videos:
        tags = v.get("tags", [])
        if tags is None:
            tags = []
        if not isinstance(tags, list):
            raise ValueError(f"Video id={v.get('id')} tags must be a JSON array")

        conn.execute(
            """
            INSERT INTO videos (
                id, slug, title, description, genre, release_year, duration_seconds, rating,
                tags_json, thumbnail_url, video_path, created_at, updated_at
            )
            VALUES (
                :id, :slug, :title, :description, :genre, :release_year, :duration_seconds, :rating,
                :tags_json, :thumbnail_url, :video_path, :created_at, :updated_at
            )
            ON CONFLICT(id) DO UPDATE SET
                slug = excluded.slug,
                title = excluded.title,
                description = excluded.description,
                genre = excluded.genre,
                release_year = excluded.release_year,
                duration_seconds = excluded.duration_seconds,
                rating = excluded.rating,
                tags_json = excluded.tags_json,
                thumbnail_url = excluded.thumbnail_url,
                video_path = excluded.video_path,
                updated_at = excluded.updated_at
            ;
            """,
            {
                "id": v["id"],
                "slug": v["slug"],
                "title": v["title"],
                "description": v.get("description", ""),
                "genre": v.get("genre", ""),
                "release_year": v.get("release_year"),
                "duration_seconds": v.get("duration_seconds"),
                "rating": v.get("rating"),
                "tags_json": json.dumps(tags, ensure_ascii=False),
                "thumbnail_url": v.get("thumbnail_url", ""),
                "video_path": v.get("video_path", ""),
                "created_at": now,
                "updated_at": now,
            },
        )


# PUBLIC_INTERFACE
def init_db() -> Path:
    """Initialize the StreamFlix SQLite DB (schema + seed data) and return DB path."""
    paths = _resolve_paths()
    conn = _connect(paths.db_path)
    try:
        with conn:
            _create_schema(conn)
            _seed_users(conn)
            seed_videos = _load_seed_videos(paths.seed_videos_path)
            _seed_videos(conn, seed_videos)
        return paths.db_path
    finally:
        conn.close()


def main() -> None:
    db_path = init_db()
    print(f"✅ StreamFlix DB ready at: {db_path}")


if __name__ == "__main__":
    main()
