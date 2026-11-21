# Cau hinh truc tiep - KHONG can file .env
# Khong chia se file nay sau khi dien token that.
import os
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/Haven.db" if os.getenv("RAILWAY_ENVIRONMENT") else "Haven.db")
BACKUP_MINUTES = 30
ARCHIVE_DAYS = 30
LOG_CHANNEL_ID = 0
DASHBOARD_KEY = ""
# De trong de bot tu gui GIF tu assets/menu.gif va assets/help.gif
MENU_GIF_URL = ""
HELP_GIF_URL = ""

# Backup GIF duoc dinh kem truc tiep tu assets/backup.gif
