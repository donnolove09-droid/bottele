import os
import sqlite3
import threading
import time
import requests
from flask import Flask, jsonify, request, send_from_directory

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "data.db")
PORT = int(os.environ.get("PORT", "10000"))
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me")

app = Flask(__name__, static_folder=".")

COMMANDS = [
    ("help", "Trợ giúp"),
    ("star", "Chức năng Star"),
    ("file", "Quản lý file"),
    ("aov", "Chức năng AOV"),
    ("mod", "Chức năng Moderator"),
    ("ff", "Chức năng Free Fire"),
    ("ban", "Cấm thành viên"),
    ("unl", "Gỡ cấm thành viên"),
]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS bots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        token TEXT NOT NULL UNIQUE,
        enabled INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id INTEGER NOT NULL,
        chat_id TEXT NOT NULL,
        title TEXT,
        enabled INTEGER NOT NULL DEFAULT 1,
        UNIQUE(bot_id, chat_id),
        FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id INTEGER NOT NULL,
        chat_id TEXT NOT NULL,
        message TEXT NOT NULL,
        interval_seconds INTEGER NOT NULL DEFAULT 3600,
        enabled INTEGER NOT NULL DEFAULT 1,
        last_sent REAL DEFAULT 0
    );
    """)
    conn.commit()
    conn.close()

def auth():
    return request.headers.get("X-Admin-Key") == ADMIN_KEY

def tg(token, method, payload=None):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=payload or {},
            timeout=20
        )
        return r.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}

def send_text(token, chat_id, text, **kwargs):
    payload = {"chat_id": chat_id, "text": text}
    payload.update(kwargs)
    return tg(token, "sendMessage", payload)

def setup_commands(token):
    return tg(token, "setMyCommands", {
        "commands": [{"command": c, "description": d} for c, d in COMMANDS]
    })

def get_bot_token(bot_id):
    conn = db()
    row = conn.execute(
        "SELECT token FROM bots WHERE id=? AND enabled=1", (bot_id,)
    ).fetchone()
    conn.close()
    return row["token"] if row else None

def is_admin(token, chat_id, user_id):
    r = tg(token, "getChatMember", {"chat_id": chat_id, "user_id": user_id})
    return r.get("ok") and r.get("result", {}).get("status") in ("administrator", "creator")

def command_help():
    return (
        "📋 MENU LỆNH\n\n"
        "/help - Trợ giúp\n"
        "/star - Chức năng Star\n"
        "/file - Quản lý file\n"
        "/aov - Chức năng AOV\n"
        "/mod - Chức năng Moderator\n"
        "/ff - Chức năng Free Fire\n"
        "/ban - Cấm thành viên\n"
        "/unl - Gỡ cấm thành viên\n"
    )

def handle_update(token, update):
    msg = update.get("message") or update.get("edited_message")
    if not msg or "text" not in msg:
        return

    text = msg["text"].strip()
    if not text.startswith("/"):
        return

    raw = text.split()[0]
    command = raw[1:].split("@")[0].lower()
    args = text.split()[1:]
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    user_id = user.get("id")
    reply_to = msg.get("message_id")

    if command == "help" or command == "commands":
        send_text(token, chat_id, command_help(), reply_to_message_id=reply_to)

    elif command == "star":
        send_text(token, chat_id, "⭐ STAR\n\nChức năng Star đang sẵn sàng.", reply_to_message_id=reply_to)

    elif command == "file":
        send_text(token, chat_id, "📁 FILE\n\nDùng dashboard để quản lý và gửi file. Chức năng upload có thể mở rộng thêm.", reply_to_message_id=reply_to)

    elif command == "aov":
        send_text(token, chat_id, "🎮 AOV\n\nMenu AOV đang sẵn sàng.", reply_to_message_id=reply_to)

    elif command == "ff":
        send_text(token, chat_id, "🔥 FREE FIRE\n\nMenu Free Fire đang sẵn sàng.", reply_to_message_id=reply_to)

    elif command == "mod":
        if is_admin(token, chat_id, user_id):
            send_text(
                token, chat_id,
                "🛡️ MODERATOR\n\n"
                "/ban - Ban thành viên\n"
                "/unl - Gỡ ban\n"
                "/status - Kiểm tra bot",
                reply_to_message_id=reply_to
            )
        else:
            send_text(token, chat_id, "⛔ Lệnh này chỉ dành cho quản trị viên.", reply_to_message_id=reply_to)

    elif command == "status":
        send_text(token, chat_id, "🟢 Bot đang hoạt động.", reply_to_message_id=reply_to)

    elif command in ("ban", "unl"):
        if not is_admin(token, chat_id, user_id):
            send_text(token, chat_id, "⛔ Bạn cần là quản trị viên để dùng lệnh này.", reply_to_message_id=reply_to)
            return

        target_id = None
        if msg.get("reply_to_message"):
            target_id = msg["reply_to_message"].get("from", {}).get("id")
        elif args:
            try:
                target_id = int(args[0])
            except ValueError:
                pass

        if not target_id:
            send_text(
                token, chat_id,
                f"ℹ️ Dùng /{command} bằng cách reply tin nhắn của thành viên "
                f"hoặc: /{command} USER_ID",
                reply_to_message_id=reply_to
            )
            return

        if command == "ban":
            result = tg(token, "banChatMember", {
                "chat_id": chat_id,
                "user_id": target_id
            })
            answer = "✅ Đã ban thành viên." if result.get("ok") else "❌ Không thể ban: " + str(result.get("description", "unknown"))
        else:
            result = tg(token, "unbanChatMember", {
                "chat_id": chat_id,
                "user_id": target_id,
                "only_if_banned": True
            })
            answer = "✅ Đã gỡ ban." if result.get("ok") else "❌ Không thể gỡ ban: " + str(result.get("description", "unknown"))

        send_text(token, chat_id, answer, reply_to_message_id=reply_to)

def poll_bot(bot_id, token):
    offset = 0
    setup_commands(token)
    while True:
        try:
            result = tg(token, "getUpdates", {
                "offset": offset,
                "timeout": 25,
                "allowed_updates": ["message"]
            })
            if result.get("ok"):
                for update in result.get("result", []):
                    offset = max(offset, update["update_id"] + 1)
                    handle_update(token, update)
        except Exception:
            time.sleep(3)

def start_pollers():
    conn = db()
    rows = conn.execute("SELECT id,token FROM bots WHERE enabled=1").fetchall()
    conn.close()
    for row in rows:
        threading.Thread(
            target=poll_bot,
            args=(row["id"], row["token"]),
            daemon=True
        ).start()

@app.before_request
def protect_api():
    if request.path.startswith("/api/") and not auth():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

@app.get("/")
def index():
    return send_from_directory(APP_DIR, "index.html")

@app.get("/api/bots")
def bots():
    conn = db()
    rows = conn.execute("SELECT id,name,enabled FROM bots ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(x) for x in rows])

@app.post("/api/bots")
def add_bot():
    data = request.json or {}
    name, token = data.get("name", "").strip(), data.get("token", "").strip()
    if not name or not token:
        return jsonify({"ok": False, "error": "name và token là bắt buộc"}), 400

    me = tg(token, "getMe")
    if not me.get("ok"):
        return jsonify({"ok": False, "error": "Bot token không hợp lệ", "telegram": me}), 400

    commands = setup_commands(token)
    conn = db()
    try:
        cur = conn.execute(
            "INSERT INTO bots(name,token) VALUES(?,?)", (name, token)
        )
        conn.commit()
        bot_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"ok": False, "error": "Token đã tồn tại"}), 409
    conn.close()

    threading.Thread(target=poll_bot, args=(bot_id, token), daemon=True).start()
    return jsonify({"ok": True, "id": bot_id, "bot": me["result"], "commands": commands})

@app.delete("/api/bots/<int:bot_id>")
def delete_bot(bot_id):
    conn = db()
    conn.execute("DELETE FROM chats WHERE bot_id=?", (bot_id,))
    conn.execute("DELETE FROM schedules WHERE bot_id=?", (bot_id,))
    conn.execute("DELETE FROM bots WHERE id=?", (bot_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.post("/api/bots/<int:bot_id>/commands")
def reset_commands(bot_id):
    token = get_bot_token(bot_id)
    if not token:
        return jsonify({"ok": False, "error": "Bot không tồn tại hoặc đang tắt"}), 404
    return jsonify(setup_commands(token))

@app.get("/api/bots/<int:bot_id>/chats")
def chats(bot_id):
    conn = db()
    rows = conn.execute(
        "SELECT id,chat_id,title,enabled FROM chats WHERE bot_id=? ORDER BY id DESC",
        (bot_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(x) for x in rows])

@app.post("/api/bots/<int:bot_id>/check-chat")
def check_chat(bot_id):
    data = request.json or {}
    chat_id = str(data.get("chat_id", "")).strip()
    if not chat_id:
        return jsonify({"ok": False, "error": "Thiếu chat_id"}), 400
    token = get_bot_token(bot_id)
    if not token:
        return jsonify({"ok": False, "error": "Bot không tồn tại"}), 404

    result = tg(token, "getChat", {"chat_id": chat_id})
    if not result.get("ok"):
        return jsonify(result), 400

    title = result["result"].get("title") or result["result"].get("username") or "Chat"
    conn = db()
    conn.execute("""
        INSERT INTO chats(bot_id,chat_id,title) VALUES(?,?,?)
        ON CONFLICT(bot_id,chat_id) DO UPDATE SET title=excluded.title
    """, (bot_id, chat_id, title))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "chat": result["result"]})

@app.get("/api/bots/<int:bot_id>/chat/<path:chat_id>/permissions")
def permissions(bot_id, chat_id):
    token = get_bot_token(bot_id)
    if not token:
        return jsonify({"ok": False, "error": "Bot không tồn tại"}), 404
    me = tg(token, "getMe")
    if not me.get("ok"):
        return jsonify(me)
    return jsonify(tg(token, "getChatMember", {
        "chat_id": chat_id, "user_id": me["result"]["id"]
    }))

@app.post("/api/send")
def send_message():
    data = request.json or {}
    bot_id = data.get("bot_id")
    chat_id = str(data.get("chat_id", ""))
    message = data.get("message", "")
    if not bot_id or not chat_id or not message:
        return jsonify({"ok": False, "error": "Thiếu bot_id/chat_id/message"}), 400
    token = get_bot_token(bot_id)
    if not token:
        return jsonify({"ok": False, "error": "Bot không tồn tại hoặc đang tắt"}), 404
    return jsonify(send_text(token, chat_id, message))

@app.get("/api/schedules")
def schedules():
    conn = db()
    rows = conn.execute("""
        SELECT s.*,b.name bot_name FROM schedules s
        JOIN bots b ON b.id=s.bot_id ORDER BY s.id DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(x) for x in rows])

@app.post("/api/schedules")
def add_schedule():
    d = request.json or {}
    required = ["bot_id", "chat_id", "message", "interval_seconds"]
    if any(k not in d for k in required):
        return jsonify({"ok": False, "error": "Thiếu dữ liệu"}), 400
    try:
        interval = max(60, int(d["interval_seconds"]))
    except Exception:
        return jsonify({"ok": False, "error": "interval_seconds không hợp lệ"}), 400

    conn = db()
    conn.execute("""
        INSERT INTO schedules(bot_id,chat_id,message,interval_seconds)
        VALUES(?,?,?,?)
    """, (d["bot_id"], str(d["chat_id"]), d["message"], interval))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.delete("/api/schedules/<int:sid>")
def delete_schedule(sid):
    conn = db()
    conn.execute("DELETE FROM schedules WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

def scheduler():
    while True:
        try:
            now = time.time()
            conn = db()
            rows = conn.execute("""
                SELECT s.*,b.token FROM schedules s
                JOIN bots b ON b.id=s.bot_id
                WHERE s.enabled=1 AND b.enabled=1
            """).fetchall()
            for r in rows:
                if now - float(r["last_sent"] or 0) >= int(r["interval_seconds"]):
                    res = send_text(r["token"], r["chat_id"], r["message"])
                    if res.get("ok"):
                        conn.execute(
                            "UPDATE schedules SET last_sent=? WHERE id=?",
                            (now, r["id"])
                        )
                        conn.commit()
            conn.close()
        except Exception:
            pass
        time.sleep(10)

init_db()
threading.Thread(target=scheduler, daemon=True).start()
start_pollers()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
