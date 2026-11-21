"""Create a consistent SQLite snapshot (run in Railway shell or locally)."""
import os, sqlite3, pathlib, datetime
from config import DATABASE_PATH
src = os.getenv("DATABASE_PATH") or DATABASE_PATH
folder = pathlib.Path(os.getenv("BACKUP_DIR", "/data/snapshots" if os.getenv("RAILWAY_ENVIRONMENT") else "snapshots"))
folder.mkdir(parents=True, exist_ok=True)
output = folder / ("all4u-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S") + ".db")
with sqlite3.connect(src) as source, sqlite3.connect(str(output)) as target:
    source.backup(target)
print(f"SQLite snapshot created: {output}")
