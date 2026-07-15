import requests
import re
import os
import tempfile
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

# ---------- CONFIG ----------
BOT_TOKEN = "8785333123:AAEzR0HtOs2lWw-rUqEofq2OZnmtO5qg23Q"
CHANNEL_ID = -1004441957969

# ---------- INIT ----------
app = Flask(__name__)
bot_app = Application.builder().token(BOT_TOKEN).build()
temp_files = {}

logging.basicConfig(level=logging.INFO)

# ---------- HELPERS ----------
async def is_user_joined(user_id):
    try:
        member = await bot_app.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def extract_video_url(terabox_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(terabox_url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return None
        
        # Pattern 1: JSON video_url
        match = re.search(r'"video_url":"([^"]+)"', resp.text)
        if match:
            return match.group(1).replace("\\/", "/")
        
        # Pattern 2: source tag
        match = re.search(r'<source[^>]+src="([^"]+)"', resp.text)
        if match:
            return match.group(1)
        
        return None
    except:
        return None

# ---------- HANDLERS ----------
async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/terabotupdates")],
        [InlineKeyboardButton("✅ Verify", callback_data="verify")]
    ]
    await update.message.reply_text(
        "🙏 **Welcome! Please join our channel to use this bot.**\n\n"
        "📢 @terabotupdates\n\n"
        "✅ After joining, press **Verify**.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def verify(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if await is_user_joined(user_id):
        await query.edit_message_text(
            "✅ **Verified!**\n\nSend me a Terabox video link.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.edit_message_text(
            "❌ **Not joined yet.**\n\nPlease join and then press Verify.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url="https://t.me/terabotupdates")],
                [InlineKeyboardButton("✅ Verify", callback_data="verify")]
            ]),
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_link(update, context):
    user_id = update.effective_user.id

    # Check if user joined
    if not await is_user_joined(user_id):
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url="https://t.me/terabotupdates")]]
        await update.message.reply_text(
            "❌ Please join the channel first.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    link = update.message.text
    if "terabox" not in link.lower():
        await update.message.reply_text("❌ Send a valid Terabox link.")
        return

    msg = await update.message.reply_text("⏳ Processing...")
    
    # Get video URL
    video_url = extract_video_url(link)
    if not video_url:
        await msg.edit_text("❌ Could not extract video. Try another link.")
        return

    # Download
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            response = requests.get(video_url, stream=True, timeout=60)
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
            file_path = tmp.name
    except:
        await msg.edit_text("❌ Download failed.")
        return

    # Send video
    caption = "⚠️ **This video will be deleted in 2 minutes.**\n💾 Save or forward it now."
    sent_msg = await update.message.reply_video(
        video=open(file_path, "rb"),
        caption=caption,
        parse_mode=ParseMode.MARKDOWN
    )

    temp_files[sent_msg.message_id] = file_path

    # Schedule deletion
    context.job_queue.run_once(
        delete_video_job,
        120,  # 2 minutes
        chat_id=update.effective_chat.id,
        message_id=sent_msg.message_id,
        file_path=file_path
    )

    await msg.edit_text("✅ Video sent! It will auto-delete in 2 minutes.")

# ---------- DELETE JOB ----------
async def delete_video_job(context):
    job = context.job
    chat_id = job.data["chat_id"]
    message_id = job.data["message_id"]
    file_path = job.data["file_path"]

    temp_files.pop(message_id, None)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="🗑️ Video deleted (2 minutes passed)."
    )

# ---------- FLASK ROUTES ----------
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

# ---------- REGISTER HANDLERS ----------
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(verify, pattern="verify"))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

# ---------- MAIN ----------
if __name__ == "__main__":
    # Set webhook
    webhook_url = "https://terabot-final.onrender.com/webhook"
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
        )
        logging.info(f"Webhook set: {resp.json()}")
    except Exception as e:
        logging.error(f"Webhook set error: {e}")

    app.run(host="0.0.0.0", port=10000)
