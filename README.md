# All4u - Hoang Tu Mua Dong (No .env)

1. Mo `config.py`, dien bot token vao `DISCORD_TOKEN`. Khong chia se token.
2. Bat **Message Content Intent** va **Server Members Intent** tren Discord Developer Portal.
3. Windows: chay `start.bat`; hoac `pip install -r requirements.txt` va `python main.py`.
4. Railway: day ma nguon len repo rieng tu (khong commit token), lenh start `python main.py`. Neu su dung Railway, nen cap token bang Railway Variables va dieu chinh config.py de doc bien moi truong thay vi commit token. Dich vu can chay lien tuc, khong duoc sleep.
5. `?menu` va `?help` tu dong dinh kem GIF trong `assets/`. Khong can MENU_GIF_URL/HELP_GIF_URL.
6. `tabo` tag owner ID 731742317010223154.
7. Database SQLite nam trong `all4u.db`. Tren hosting ephemeral, can volume de giu backup, warnings va settings qua deploy/restart.

Luu y: chua kiem thu truc tiep tren Discord.

8. `?message_restore 5`: bot tra loi lenh tren kenh hien tai bang 5 ban sao tin nhan da luu, kem ten nguoi gui va thoi gian. Chi nguoi co quyen Manage Messages moi dung duoc. Gioi han 1-20 tin/lan. Khong ping, khong khoi phuc message ID/reactions/attachments hay tin nhan truoc khi bot luu.

9. `?message_restore 5` tag ID nguoi gui goc trong kenh va kem noi dung tin nhan da luu. Co the gui thong bao ping den nguoi duoc tag; khong ping role/everyone.

10. Tat ca phan hoi lenh duoc gui cong khai trong kenh, khong ephemeral/DM. Nut Security hien thong bao quyen cong khai. `?backup_export` chi dang tep trong kenh an voi @everyone de tranh lo thong tin kenh rieng.


## Server Recovery + Anti-Rogue Bot
- `?recovery_full [backup_id]`: phục hồi các role, category, text/voice channel **bị thiếu**; không xóa dữ liệu hiện có.
- `?recovery_status`, `?recovery_cancel`, `?recovery_messages [1-20]`.
- `?antibot on/off`, `?antibot_status`, `?antibot_whitelist add/remove/list <bot_id>`.
- Anti-Rogue Bot chỉ kick bot (không kick người) khi Audit Log xác nhận >=3 hành động xóa/sửa role/kênh trong 20 giây. Không xử lý bot tin cậy hoặc bot có role cao hơn All4u.
- Bật View Audit Log, Kick Members, Manage Channels, Manage Roles và Server Members Intent, Message Content Intent.
- Trên Railway đặt `DISCORD_TOKEN` bằng Variables, `DATABASE_PATH=/data/all4u.db`, tạo Volume tại `/data`. Không commit token lên GitHub.
- Backup cấu trúc hiện tại không lưu channel permission overwrites, member-role assignments, attachments hoặc ID gốc. Full recovery không thể phục hồi chính xác các phần chưa sao lưu.


## Backup panel
`?backup` mo bang Backup & Recovery kem GIF Violet Evergarden trong `assets/backup.gif`. `?backup_create` tao backup thu cong. `?help` va `?menu` giu nguyen GIF rieng.
