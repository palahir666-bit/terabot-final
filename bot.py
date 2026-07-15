import requests, re, time, os, tempfile
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

BOT_TOKEN = "8785333123:AAEzR0HtOs2lWw-rUqEofq2OZnmtO5qg23Q"
CHANNEL_USERNAME = "@terabotupdates"
CHANNEL_ID = -1004441957969

temp_files = {}
app = Flask(__name__)
bot_app = Application.builder().token(BOT_TOKEN).build()

# ---------- Check Join ----------
async def is_user_joined(user_id):
    try:
        member = await bot_app.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ---------- /start ----------
async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("📢 Channel Join", url="https://t.me/terabotupdates")],
        [InlineKeyboardButton("✅ Verify", callback_data="verify")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🙏 **Dhanyavaad! Hamara bot use karne ke liye.**\n\n"
        "📢 **Kripya niche diya gaya channel join karein:**\n"
        "🔗 @terabotupdates\n\n"
        "✅ **Channel join karne ke baad 'Verify' dabayein.**",
        reply_markup=reply_markup
    )

# ---------- Verify Callback ----------
async def verify(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if await is_user_joined(user_id):
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

# ---------- Handle Link ----------
async def handle_link(update, context):
    user_id = update.effective_user.id

    if not await is_user_joined(user_id):
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
        time.sleep(1)
        await msg.edit_text(f"⏳ Downloading {'•' * i}")

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
    caption = (
        "⚠️ **Yeh video 2 minute baad delete ho jayegi.**\n"
        "💾 **Save karein ya forward karein.**"
    )
    sent_msg = await update.message.reply_video(video=open(file_path, "rb"), caption=caption)
    temp_files[sent_msg.message_id] = file_path

    bot_app.job_queue.run_once(
        delete_video, 120,
        chat_id=update.effective_chat.id,
        message_id=sent_msg.message_id
    )
    await msg.edit_text("✅ Video aa gayi! ⏳ 2 minute ka time hai.")

# ---------- Delete Video ----------
async def delete_video(context):
    job_data = context.job.data
    file_path = temp_files.pop(job_data['message_id'], None)
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    await bot_app.bot.send_message(
        chat_id=job_data['chat_id'],
        text="🗑️ **Video delete ho gayi.**"
    )

# ---------- Terabox Extractor ----------
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

# ---------- Flask Webhook ----------
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    bot_app.process_update(update)
    return 'ok', 200

@app.route('/')
def home():
    return "Bot is running!"

# ---------- Handlers ----------
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(verify, pattern="verify"))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

# ---------- Start ----------
if __name__ == '__main__':
    # YAHAN APNI RENDER URL DAALO
    bot_app.bot.set_webhook(url='https://terabot-1-pwql.onrender.com/webhook')
    app.run(host='0.0.0.0', port=10000)
