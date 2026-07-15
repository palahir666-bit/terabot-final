import requests, re, time, os, tempfile, asyncio, json
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

BOT_TOKEN = "8785333123:AAEzR0HtOs2lWw-rUqEofq2OZnmtO5qg23Q"
CHANNEL_USERNAME = "@terabotupdates"
CHANNEL_ID = -1004441957969

temp_files = {}
app = Flask(__name__)
bot_app = None

# ---------- Initialize Bot ----------
async def init_bot():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(verify, pattern="verify"))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    return bot_app

# ---------- Check Join ----------
async def is_user_joined(user_id):
    try:
        member = await bot_app.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Error checking member: {e}")
        return False

# ---------- /start ----------
async def start(update: Update, context):
    try:
        keyboard = [
            [InlineKeyboardButton("📢 Channel Join", url="https://t.me/terabotupdates")],
            [InlineKeyboardButton("✅ Verify", callback_data="verify")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🙏 *Dhanyavaad! Hamara bot use karne ke liye.*\n\n"
            "📢 *Kripya niche diya gaya channel join karein:*\n"
            "🔗 @terabotupdates\n\n"
            "✅ *Channel join karne ke baad 'Verify' dabayein.*",
            reply_markup=reply_markup,
            parse_mode=constants.ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"Error in start: {e}")

# ---------- Verify Callback ----------
async def verify(update: Update, context):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if await is_user_joined(user_id):
            await query.edit_message_text(
                "✅ *Verification successful!*\n\n"
                "📎 *Ab Terabox video link bhejiye.*",
                parse_mode=constants.ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(
                "❌ *Aap channel join nahi karein hain.*\n\n"
                "📢 *Pehle channel join karein, phir Verify dabayein.*",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Channel Join", url="https://t.me/terabotupdates")],
                    [InlineKeyboardButton("✅ Verify", callback_data="verify")]
                ]),
                parse_mode=constants.ParseMode.MARKDOWN
            )
    except Exception as e:
        print(f"Error in verify: {e}")

# ---------- Handle Link ----------
async def handle_link(update: Update, context):
    try:
        user_id = update.effective_user.id

        if not await is_user_joined(user_id):
            keyboard = [
                [InlineKeyboardButton("📢 Channel Join", url="https://t.me/terabotupdates")],
                [InlineKeyboardButton("✅ Verify", callback_data="verify")]
            ]
            await update.message.reply_text(
                "❌ *Pehle channel join karein aur verify karein.*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=constants.ParseMode.MARKDOWN
            )
            return

        link = update.message.text
        if "terabox" not in link.lower():
            await update.message.reply_text(
                "❌ Sirf Terabox link bhejo.",
                parse_mode=constants.ParseMode.MARKDOWN
            )
            return

        msg = await update.message.reply_text("⏳ Video dhundh raha hu...")
        
        # Show progress
        for i in range(1, 6):
            await asyncio.sleep(0.5)
            await msg.edit_text(f"⏳ Downloading {'•' * i}")

        # Get direct link
        video_url = await asyncio.to_thread(get_terabox_direct_link, link)
        if not video_url:
            await msg.edit_text(
                "❌ Video link nahi mila ya link invalid hai.",
                parse_mode=constants.ParseMode.MARKDOWN
            )
            return

        await msg.edit_text(
            "📥 Download ho raha hai...",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        
        # Download video
        try:
            file_path = await asyncio.to_thread(download_video, video_url)
            if not file_path:
                await msg.edit_text(
                    "❌ Download fail.",
                    parse_mode=constants.ParseMode.MARKDOWN
                )
                return
        except Exception as e:
            print(f"Download error: {e}")
            await msg.edit_text(
                "❌ Download fail.",
                parse_mode=constants.ParseMode.MARKDOWN
            )
            return

        await msg.edit_text(
            "📤 Video send kar raha hu...",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        
        # Send video
        caption = "⚠️ *Yeh video 2 minute baad delete ho jayegi.*\n💾 *Save karein ya forward karein.*"
        try:
            with open(file_path, "rb") as video_file:
                sent_msg = await update.message.reply_video(
                    video=video_file,
                    caption=caption,
                    parse_mode=constants.ParseMode.MARKDOWN
                )
            
            temp_files[sent_msg.message_id] = file_path
            
            # Schedule deletion
            asyncio.create_task(delete_video_after_delay(
                update.effective_chat.id,
                sent_msg.message_id,
                file_path,
                context.bot
            ))
            
            await msg.edit_text(
                "✅ Video aa gayi! ⏳ 2 minute ka time hai.",
                parse_mode=constants.ParseMode.MARKDOWN
            )
        except Exception as e:
            print(f"Send video error: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
            await msg.edit_text(
                "❌ Video send nahi ho saki.",
                parse_mode=constants.ParseMode.MARKDOWN
            )

    except Exception as e:
        print(f"Error in handle_link: {e}")
        try:
            await update.message.reply_text(
                "❌ Kuch galti hua. Dobara try karein.",
                parse_mode=constants.ParseMode.MARKDOWN
            )
        except:
            pass

# ---------- Download Video ----------
def download_video(video_url):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            response = requests.get(video_url, stream=True, timeout=60)
            response.raise_for_status()
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
            
            return tmp.name
    except Exception as e:
        print(f"Download video error: {e}")
        return None

# ---------- Delete Video ----------
async def delete_video_after_delay(chat_id, message_id, file_path, bot):
    try:
        await asyncio.sleep(120)  # 2 minutes
        
        # Delete from temp_files dict
        temp_files.pop(message_id, None)
        
        # Delete file
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        # Notify user
        await bot.send_message(
            chat_id=chat_id,
            text="🗑️ *Video delete ho gayi.*",
            parse_mode=constants.ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"Error deleting video: {e}")

# ---------- Terabox Extractor ----------
def get_terabox_direct_link(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            return None
        
        # Try to find video_url in JSON format
        try:
            if '"video_url":"' in resp.text:
                match = re.search(r'"video_url":"([^"]+)"', resp.text)
                if match:
                    video_url = match.group(1).replace("\\/", "/")
                    return video_url
        except:
            pass
        
        # Try to find source tag
        try:
            match = re.search(r'<source[^>]+src="([^"]+)"', resp.text)
            if match:
                return match.group(1)
        except:
            pass
        
        return None
    except Exception as e:
        print(f"Terabox extraction error: {e}")
        return None

# ---------- Flask Webhook ----------
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, bot_app.bot)
        
        # Create new event loop for this request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.process_update(update))
        loop.close()
        
        return 'ok', 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return 'error', 500

@app.route('/')
def home():
    return "🤖 Bot is running!", 200

# ---------- Start ----------
if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_app = loop.run_until_complete(init_bot())
    
    # Set webhook
    try:
        webhook_url = "https://terabot-final.onrender.com/webhook"
        resp = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            params={"url": webhook_url},
            timeout=10
        )
        print(f"Webhook setup response: {resp.json()}")
    except Exception as e:
        print(f"Webhook setup error: {e}")
    
    # Run Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    
