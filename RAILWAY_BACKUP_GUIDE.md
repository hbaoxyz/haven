# All4u — Railway deploy and backup

## 1. Deploy
Upload the contents of this folder to a private GitHub repository (not the outer ZIP). Set Railway start command to `python main.py`; use one replica. Set `DISCORD_TOKEN` as a Railway service variable (never commit the real token). Enable Message Content Intent and Server Members Intent in Discord Developer Portal.

## 2. Persistent storage
Attach a Railway Volume to the same service, mount path `/data`. Set Railway variable `DATABASE_PATH=/data/all4u.db`. Redeploy. `config.py` defaults to this path when `RAILWAY_ENVIRONMENT` is present; locally it defaults to `all4u.db`.

## 3. What is saved
SQLite stores bot settings, archived messages, warnings, trusted lists, server structure backups, recovery job status and anti-bot allowlist. `?backup_create` saves server structure into SQLite; automatic structure backup runs every 30 minutes while bot is online. `?backup_list`, `?restore_preview`, `?restore_missing`, `?recovery_full` manage that structure. Archived messages are retained for 30 days as configured, and can only restore content previously captured.

## 4. Independent snapshots
Volume persistence is NOT an offsite backup. `python backup_database.py` creates a consistent SQLite snapshot at `/data/snapshots/all4u-YYYYMMDD-HHMMSS.db` when run inside Railway. This is ON THE SAME VOLUME, so copy snapshots to independent storage periodically (e.g. S3-compatible bucket) and test restoring them. No automatic offsite upload is included. Avoid copying live `all4u.db` directly while SQLite is running; use the snapshot script.

## 5. Restore the database
Stop the bot before replacing `/data/all4u.db` with a verified snapshot, keep an additional copy of the current database, and restart. Do not overwrite while the bot is connected. If you have data in an older `all4u.db`, migrate it into the volume before switching paths.

## 6. Security and verification
Check Deploy Logs for successful login; `discord.errors.LoginFailure: Improper token has been passed` means token configuration is wrong, not storage. Test `?ping`, `?help`, `?menu`, `?backup`, `?backup_create`, `?backup_list`. Never publish DB snapshots or token.
