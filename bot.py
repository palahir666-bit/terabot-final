import requests, re, time, os, tempfile, asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackQueryHandler, Dispatcher

BOT_TOKEN = "8785333123:AAEzR0HtOs2lWw-rUqEofq2OZnmtO5qg23Q"
CHANNEL_USERNAME = "@terabotupdates"
CHANNEL_ID = -1004441957969

temp_files = {}
app = Flask(__name__)

# ---------- Async Helpers ----------
async def is_user_joined(user_id, bot):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

async def delete_video_after_delay(chat_id, message_id, bot, delay=120):
    await asyncio.sleep(delay)
    file_path = temp_files.pop(message_id, None)
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    await bot.send_message(chat_id=chat_id, text="🗑️ **Video delete ho gayi.**")

# ---------- Handlers ----------
async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("📢 Channel Join", url="https://t.me/terabotupdates")],
        [InlineKeyboardButton("✅ Verify", callback_data="verify")]
    ]
    await update.message.reply_text(
        "🙏 **Dhanyavaad! Hamara bot use karne ke liye.**\n\n"
        "📢 **Kripya niche diya gaya channel join karein:**\n"
        "🔗 @terabotupdates\n\n"
        "✅ **Channel join karne ke baad 'Verify' dabayein.**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def verify(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bot = context.bot

    if await is_user_joined(user_id, bot):
        await query.edit_message_text(
            "✅ **Verification successful!**\n\n"
            "📎 **Ab Terabox video link bhejiye.**"
        )
    else:
        await query.edit_message_text(
            "❌ **Aap channel join nahi karein hain.**\n\n"
            "📢 **Pehle channel join karein, phir Verify dabayein.**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Channel Join", url="https://t.me/terabotupdates")],
                [InlineKeyboardButton("✅ Verify", callback_data="verify")]
            ])
        )

async def handle_link(update, context):
    user_id = update.effective_user.id
    bot = context.bot

    if not await is_user_joined(user_id, bot):
        keyboard = [
            [InlineKeyboardButton("📢 Channel Join", url="https://t.me/terabotupdates")],
            [InlineKeyboardButton("✅ Verify", callback_data="verify")]
        ]
        await update.message.reply_text(
            "❌ **Pehle channel join karein aur verify karein.**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    link = update.message.text
    if "terabox" not in link.lower():
        await update.message.reply_text("❌ Sirf Terabox link bhejo.")
        return

    msg = await update.message.reply_text("⏳ Video dhundh raha hu...")
    for i in range(1, 6):
        await asyncio.sleep(1)
        await msg.edit_text(f"⏳ Downloading {'•' * i}")

    # Extract video
    video_url = get_terabox_direct_link(link)
    if not video_url:
        await msg.edit_text("❌ Video link nahi mila.")
        return

    await msg.edit_text("📥 Download ho raha hai...")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            response = requests.get(video_url, stream=True, timeout=60)
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
            file_path = tmp.name
    except:
        await msg.edit_text("❌ Download fail.")
        return

    await msg.edit_text("📤 Video send kar raha hu...")
    caption = "⚠️ **Yeh video 2 minute baad delete ho jayegi.**\n💾 **Save karein ya forward karein.**"
    sent_msg = await update.message.reply_video(video=open(file_path, "rb"), caption=caption)
    temp_files[sent_msg.message_id] = file_path

    # Auto-delete after 2 minutes
    asyncio.create_task(delete_video_after_delay(update.effective_chat.id, sent_msg.message_id, bot, 120))
    await msg.edit_text("✅ Video aa gayi! ⏳ 2 minute ka time hai.")

def get_terabox_direct_link(url):
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.terabox.com/"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
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

# ---------- Flask Webhook Setup ----------
dispatcher = Dispatcher(bot=None, update_queue=None)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(verify, pattern="verify"))
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), None)
    asyncio.run(dispatcher.process_update(update))
    return 'ok', 200

@app.route('/')
def home():
    return "Bot is running!"

if __name__ == '__main__':
    # Webhook set karo
    import requests as req
    webhook_url = "https://terabot-final.onrender.com/webhook"
    set_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    req.get(set_url)
    app.run(host='0.0.0.0', port=10000)
