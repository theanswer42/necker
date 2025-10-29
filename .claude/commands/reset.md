---
description: Reset database by deleting data directory and running migrations
---

Run the reset script to delete the data directory and recreate the database with migrations:

```bash
uv run python -m scripts.reset
```

This will:
1. Show what will be deleted (data directory, database, logs, archives)
2. Ask for confirmation
3. Delete the data directory
4. Run migrations to create a fresh database
