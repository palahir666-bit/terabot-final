import os, logging, requests, re, tempfile, time, json
from flask import Flask, request

BOT_TOKEN = "8785333123:AAEzR0HtOs2lWw-rUqEofq2OZnmtO5qg23Q"
CHANNEL_ID = -1004441957969

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ---------- SEND MESSAGE ----------
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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Send error: {e}")

# ---------- SEND VIDEO ----------
def send_video(chat_id, file_path, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    try:
        with open(file_path, "rb") as f:
            files = {"video": f}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            requests.post(url, data=data, files=files, timeout=60)
    except Exception as e:
        logging.error(f"Send video error: {e}")

# ---------- CHECK JOIN ----------
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

# ---------- EXTRACT VIDEO URL ----------
def extract_video_url(terabox_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(terabox_url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return None
        match = re.search(r'"video_url":"([^"]+)"', resp.text)
        if match:
            return match.group(1).replace("\\/", "/")
        match = re.search(r'<source[^>]+src="([^"]+)"', resp.text)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        logging.error(f"Extract error: {e}")
        return None

# ---------- DOWNLOAD VIDEO ----------
def download_video(video_url):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            response = requests.get(video_url, stream=True, timeout=60)
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
            return tmp.name
    except Exception as e:
        logging.error(f"Download error: {e}")
        return None

# ---------- WEBHOOK ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        logging.info(f"Webhook received")

        # ---------- MESSAGE ----------
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
                if not is_user_joined(user_id):
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "📢 Join Channel", "url": "https://t.me/terabotupdates"}],
                            [{"text": "✅ Verify", "callback_data": "verify"}]
                        ]
                    }
                    send_message(chat_id, "❌ Please join the channel first.", keyboard)
                    return "ok", 200

                send_message(chat_id, "⏳ Extracting video link...")
                video_url = extract_video_url(text)
                if not video_url:
                    send_message(chat_id, "❌ Could not extract video. Try another link.")
                    return "ok", 200

                send_message(chat_id, "📥 Downloading video...")
                file_path = download_video(video_url)
                if not file_path:
                    send_message(chat_id, "❌ Download failed.")
                    return "ok", 200

                caption = "⚠️ **This video will be deleted in 2 minutes.**\n💾 Save or forward it now."
                send_video(chat_id, file_path, caption)
                
                # Schedule deletion
                threading.Thread(target=delete_video_after, args=(file_path, chat_id), daemon=True).start()
                
                send_message(chat_id, "✅ Video sent! Auto-delete in 2 min.")
            else:
                send_message(chat_id, "❌ Send a valid Terabox link.")

        # ---------- CALLBACK QUERY ----------
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

# ---------- DELETE VIDEO (Background Thread) ----------
def delete_video_after(file_path, chat_id):
    time.sleep(120)
    if os.path.exists(file_path):
        os.remove(file_path)
    send_message(chat_id, "🗑️ Video deleted (2 minutes passed).")

# ---------- HOME ----------
@app.route("/")
def home():
    return "🤖 Bot is running!", 200

# ---------- MAIN ----------
if __name__ == "__main__":
    # Set webhook
    webhook_url = "https://terabot-final-5.onrender.com/webhook"
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
