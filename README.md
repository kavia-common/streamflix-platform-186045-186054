# streamflix-platform-186045-186054

## streaming_database (SQLite)

This workspace contains the StreamFlix SQLite database container.

### Deterministic SQLite file path

The database is created at:

- `streaming_database/data/streamflix.sqlite3`

Initialize schema + seed data (idempotent):

```bash
cd streamflix-platform-186045-186054/streaming_database
python3 init_db.py
```

Connection instructions:

- `streaming_database/db_connection.txt`
- `streaming_database/README.md`