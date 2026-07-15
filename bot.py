import os, logging, requests, re, tempfile
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode

BOT_TOKEN = "8785333123:AAEzR0HtOs2lWw-rUqEofq2OZnmtO5qg23Q"
CHANNEL_ID = -1004441957969

app = Flask(__name__)
bot_app = Application.builder().token(BOT_TOKEN).build()
temp_files = {}
logging.basicConfig(level=logging.INFO)

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
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/terabotupdates")],
        [InlineKeyboardButton("✅ Verify", callback_data="verify")]
    ]
    await update.message.reply_text(
        "🙏 **Welcome! Join channel & press Verify.**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

# ---------- Verify ----------
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

# ---------- Handle Link ----------
async def handle_link(update, context):
    user_id = update.effective_user.id
    if not await is_user_joined(user_id):
        await update.message.reply_text("❌ Join channel first.")
        return

    link = update.message.text
    if "terabox" not in link.lower():
        await update.message.reply_text("❌ Send Terabox link.")
        return

    await update.message.reply_text("⏳ Processing... (Video download coming soon)")

# ---------- Webhook ----------
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

# ---------- Handlers ----------
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(verify, pattern="verify"))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

# ---------- Main ----------
if __name__ == "__main__":
    webhook_url = "https://terabot-final-2.onrender.com/webhook"
    try:
        resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}")
        logging.info(f"Webhook set: {resp.json()}")
    except Exception as e:
        logging.error(f"Webhook set error: {e}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
