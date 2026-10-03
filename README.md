# Telegram Bot Manager v2

Bản này có sẵn 8 slash commands:
- /help
- /star
- /file
- /aov
- /mod
- /ff
- /ban
- /unl

Khi thêm bot qua dashboard, hệ thống tự gọi Telegram `setMyCommands` và khởi động polling để xử lý lệnh.

## /ban và /unl
- Có thể reply tin nhắn của thành viên rồi gửi `/ban` hoặc `/unl`.
- Hoặc `/ban USER_ID` / `/unl USER_ID`.
- Người dùng gọi lệnh phải là admin.
- Bot phải có quyền quản trị nhóm phù hợp để ban/unban.

## Deploy Render
1. Upload code lên GitHub.
2. Render → New → Blueprint hoặc Web Service.
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn bot:app`
5. Environment variable: `ADMIN_KEY=<chuỗi-bí-mật-dài>`

## Lưu ý Render
SQLite trên disk cần Persistent Disk để dữ liệu không mất khi service được thay/redeploy. `render.yaml` đã khai báo disk 1GB.
