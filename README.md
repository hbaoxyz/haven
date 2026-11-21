# Haven / All4u — GIF fix

Upload **all files and the assets folder** to the ROOT of your GitHub repository.

Expected:
- main.py
- config.py
- requirements.txt
- Procfile
- assets/menu.gif
- assets/help.gif
- assets/backup.gif

Railway Variables: DISCORD_TOKEN=<secret>, DATABASE_PATH=/data/Haven.db
Railway Start Command: python main.py
Mount a persistent Volume at /data before storing valuable data.

Check Deploy Logs: GIF menu: FOUND / GIF help: FOUND / GIF backup: FOUND.
Test ?menu, ?help, ?backup. Do not publish bot tokens or database snapshots.
