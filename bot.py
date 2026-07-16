import os, logging, requests, re, tempfile, asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

BOT_TOKEN = "8785333123:AAEzR0HtOs2lWw-rUqEofq2OZnmtO5qg23Q"
CHANNEL_ID = -1004441957969

app = Flask(__name__)
bot_app = None
temp_files = {}
logging.basicConfig(level=logging.INFO)

# ---------- INIT BOT ----------
def init_bot():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(verify, pattern="verify"))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    return bot_app

# ---------- CHECK JOIN ----------
async def is_user_joined(user_id):
    try:
        member = await bot_app.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
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
    except:
        return None

# ---------- /start ----------
async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/terabotupdates")],
        [InlineKeyboardButton("✅ Verify", callback_data="verify")]
    ]
    await update.message.reply_text(
        "🙏 **Welcome! Join channel & press Verify.**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

# ---------- VERIFY ----------
async def verify(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if await is_user_joined(user_id):
        await query.edit_message_text("✅ **Verified!** Send Terabox link.", parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_text(
            "❌ **Not joined.** Join & Verify again.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join", url="https://t.me/terabotupdates")],
                [InlineKeyboardButton("✅ Verify", callback_data="verify")]
            ]),
            parse_mode=ParseMode.MARKDOWN
        )

# ---------- HANDLE LINK ----------
async def handle_link(update, context):
    user_id = update.effective_user.id
    if not await is_user_joined(user_id):
        await update.message.reply_text("❌ Join channel first.")
        return

    link = update.message.text
    if "terabox" not in link.lower():
        await update.message.reply_text("❌ Send Terabox link.")
        return

    msg = await update.message.reply_text("⏳ Extracting video link...")
    video_url = extract_video_url(link)
    if not video_url:
        await msg.edit_text("❌ Extract failed.")
        return

    await msg.edit_text("📥 Downloading...")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            response = requests.get(video_url, stream=True, timeout=60)
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
            file_path = tmp.name
    except:
        await msg.edit_text("❌ Download failed.")
        return

    await msg.edit_text("📤 Sending video...")
    caption = "⚠️ **Delete in 2 min.** Save/Forward."
    sent_msg = await update.message.reply_video(
        video=open(file_path, "rb"),
        caption=caption,
        parse_mode=ParseMode.MARKDOWN
    )
    temp_files[sent_msg.message_id] = file_path

    # Schedule deletion without job_queue
    asyncio.create_task(delete_video_after(update.effective_chat.id, sent_msg.message_id, file_path, context.bot))
    await msg.edit_text("✅ Video sent! Auto-delete in 2 min.")

# ---------- DELETE VIDEO ----------
async def delete_video_after(chat_id, message_id, file_path, bot):
    await asyncio.sleep(120)
    temp_files.pop(message_id, None)
    if os.path.exists(file_path):
        os.remove(file_path)
    await bot.send_message(chat_id=chat_id, text="🗑️ Video deleted.")

# ---------- WEBHOOK ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        bot_app.process_update(update)
        return "ok", 200
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return "error", 500

@app.route("/")
def home():
    return "🤖 Bot is running!", 200

# ---------- MAIN ----------
if __name__ == "__main__":
    bot_app = init_bot()
    webhook_url = "https://terabot-final-5.onrender.com/webhook"
    try:
        resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}")
        logging.info(f"Webhook set: {resp.json()}")
    except Exception as e:
        logging.error(f"Webhook set error: {e}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
