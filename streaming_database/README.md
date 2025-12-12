# streaming_database (SQLite)

This container holds the **deterministic SQLite database** for StreamFlix, plus an **idempotent initializer** that creates schema and seeds data.

## Deterministic DB file path

By default, the database file will be created at:

- `streaming_database/data/streamflix.sqlite3`

This deterministic location is important so the **backend container can reference the same file path** (typically via a shared volume/mount in orchestration).

You can override the path with:

- `STREAMFLIX_SQLITE_PATH=/absolute/path/to/streamflix.sqlite3`

## Initialize / seed (idempotent)

From this workspace root:

```bash
cd streamflix-platform-186045-186054/streaming_database
python3 init_db.py
```

Re-running `init_db.py` is safe:
- Tables use `IF NOT EXISTS`
- Seed data is applied via `UPSERT` (no duplicates)

## Seed data

- Videos: `streaming_database/seed/seed_videos.json`
- Users: seeded inside `init_db.py` (demo user)

Demo user (for development):
- email: `demo@streamflix.local`
- username: `demo`
- password: `password`

> Note: the password is stored as a bcrypt hash. This is intended for local development only.

## How to connect

See `db_connection.txt` for `sqlite3` and verification commands.
