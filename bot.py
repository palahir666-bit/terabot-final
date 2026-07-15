import os, logging, requests, json
from flask import Flask, request

BOT_TOKEN = "8785333123:AAEzR0HtOs2lWw-rUqEofq2OZnmtO5qg23Q"
CHANNEL_ID = -1004441957969

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ---------- Send Message ----------
def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        resp = requests.post(url, json=payload, timeout=10)
        logging.info(f"Sent: {resp.status_code}")
    except Exception as e:
        logging.error(f"Send error: {e}")

# ---------- Check Join ----------
def is_user_joined(user_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        params = {"chat_id": CHANNEL_ID, "user_id": user_id}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                status = data["result"]["status"]
                return status in ["member", "administrator", "creator"]
        return False
    except Exception as e:
        logging.error(f"Join check error: {e}")
        return False

# ---------- Webhook ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        logging.info(f"Webhook received: {data}")

        # ---------- Message ----------
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            text = msg.get("text", "")

            if text == "/start":
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📢 Join Channel", "url": "https://t.me/terabotupdates"}],
                        [{"text": "✅ Verify", "callback_data": "verify"}]
                    ]
                }
                send_message(chat_id, "🙏 **Welcome! Join channel & press Verify.**", keyboard)

            elif "terabox" in text.lower():
                if is_user_joined(user_id):
                    send_message(chat_id, "⏳ Processing video... (Download feature soon)")
                else:
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "📢 Join Channel", "url": "https://t.me/terabotupdates"}],
                            [{"text": "✅ Verify", "callback_data": "verify"}]
                        ]
                    }
                    send_message(chat_id, "❌ Please join the channel first.", keyboard)
            else:
                send_message(chat_id, "❌ Send a valid Terabox link.")

        # ---------- Callback Query ----------
        elif "callback_query" in data:
            query = data["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            user_id = query["from"]["id"]

            if query["data"] == "verify":
                if is_user_joined(user_id):
                    send_message(chat_id, "✅ **Verified!** Now send me a Terabox link.")
                else:
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "📢 Join Channel", "url": "https://t.me/terabotupdates"}],
                            [{"text": "✅ Verify", "callback_data": "verify"}]
                        ]
                    }
                    send_message(chat_id, "❌ **You haven't joined yet.** Please join and verify.", keyboard)

        return "ok", 200

    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return "error", 500

# ---------- Home ----------
@app.route("/")
def home():
    return "🤖 Bot is running!", 200

# ---------- Main ----------
if __name__ == "__main__":
    # Set webhook
    webhook_url = "https://terabot-final-2.onrender.com/webhook"
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}",
            timeout=10
        )
        logging.info(f"Webhook set: {resp.json()}")
    except Exception as e:
        logging.error(f"Webhook set error: {e}")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
