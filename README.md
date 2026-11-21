# Haven All4u — Full Server Backup

Giữ nguyên các lệnh và 3 GIF trong assets/. Sao lưu bổ sung ID role/category/channel, permission overwrites, vị trí, và role của thành viên bot nhìn thấy. `?backup_create` tạo bản sao lưu mới; `?restore_preview` xem phần thiếu; `?restore_missing` và `?recovery_full` tạo phần thiếu, áp dụng quyền kênh mới, gán lại role đã lưu khi đủ quyền. Không xóa kênh hoặc role hiện có.

Railway: `DISCORD_TOKEN` và `DATABASE_PATH=/data/Haven.db`, Volume mount `/data`, Start Command `python main.py`, 1 replica. Bật Message Content Intent và Server Members Intent. Cấp quyền Manage Roles, Manage Channels, View Audit Log; role của bot phải cao hơn role cần phục hồi. Sau khi Deploy, chạy `?backup_create` để tạo backup schema mới (backup cũ không chứa member-role/overwrites).

Giới hạn: không phục hồi được ID gốc, tin nhắn đã xóa trước khi bot lưu, file đính kèm, emoji, webhook, role managed, một số loại kênh khác Text/Voice, và các quyền không đủ để cấp. Thứ tự role hiện có không bị sửa; thứ tự các kênh mới được khôi phục ở mức tốt nhất. Tên trùng có thể gây đối sánh không chính xác. Sao lưu database ra ngoài Railway Volume định kỳ.
