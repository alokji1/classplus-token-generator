from pyrogram import Client, filters
from pyrogram.types import Message
from fastapi import FastAPI
import uvicorn
import threading
import requests
import random
import string
import time
import re

# Your Telegram bot credentials
API_ID = 26
API_HASH = "67a8f9684286baa34cb"
BOT_TOKEN = "8AFfe-alroUVCU9ttJphHe98GCS1iVxNbLI"  # ← यहाँ अपना Bot Token डालो

bot = Client("classplus_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
web = FastAPI()
user_state = {}

# Generate temp email
def generate_email():
    login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    domain = "1secmail.com"
    return f"{login}@{domain}", login, domain

def check_inbox(login, domain):
    url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
    return requests.get(url).json()

def read_message(login, domain, msg_id):
    url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}"
    return requests.get(url).json()

def extract_otp(text):
    found = re.findall(r'\b\d{4,8}\b', text)
    return found[0] if found else None

@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    email, login, domain = generate_email()
    user_state[message.from_user.id] = {
        "email": email, "login": login, "domain": domain
    }
    await message.reply_text(f"📧 Use this email to request OTP:\n`{email}`", parse_mode="markdown")

    # Poll inbox
    for _ in range(30):
        inbox = check_inbox(login, domain)
        if inbox:
            msg = read_message(login, domain, inbox[0]["id"])
            otp = extract_otp(msg["body"])
            if otp:
                await message.reply_text(f"✅ OTP Received: `{otp}`", parse_mode="markdown")

                headers = {
                    "User-Agent": "okhttp/3.12.1",
                    "Content-Type": "application/json"
                }
                payload = {
                    "deviceId": ''.join(random.choices(string.ascii_lowercase + string.digits, k=16)),
                    "otp": otp,
                    "email": email
                }
                try:
                    res = requests.post("https://api.classplusapp.com/v2/user/loginWithEmail", json=payload, headers=headers)
                    if res.status_code == 200 and "data" in res.json():
                        token = res.json()["data"]["token"]
                        await message.reply_text(f"🟢 <b>Access Token:</b>\n<code>{token}</code>", parse_mode="html")
                    else:
                        await message.reply_text("❌ OTP accepted but failed to generate token.")
                except Exception as e:
                    await message.reply_text(f"⚠️ Error: {str(e)}")
                return
        time.sleep(3)
    await message.reply("⌛ Timeout: No OTP received in 90 seconds.")

@web.get("/")
def root():
    return {"status": "Bot is alive", "message": "Use me on Telegram!"}

def run_bot():
    bot.run()

# Start bot in background
threading.Thread(target=run_bot).start()

# Run FastAPI
if __name__ == "__main__":
    uvicorn.run(web, host="0.0.0.0", port=8000)
def verify_classplus(email, otp):
    payload = {
        "email": email,
        "otp": otp,
        "countryCode": "+91",
        "userType": 0
    }
    headers = {
        "x-application-id": "classplus",
        "content-type": "application/json"
    }
    r = requests.post("https://api.classplusapp.com/v2/customer/otp/verify", json=payload, headers=headers)
    if r.status_code == 200:
        return r.json().get("data", {}).get("accessToken")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send your temp email (e.g. something@1secmail.com or @kzccv.com or @datingso.com):")
    return ASK_EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    username, domain = extract_username_domain(email)
    if not username or not domain:
        await update.message.reply_text("⚠️ Invalid email format. Please send a valid email like name@domain.com")
        return ASK_EMAIL

    user_email_map[update.effective_user.id] = (email, username, domain)

    await update.message.reply_text(f"✅ Using email: <code>{email}</code>\nNow send OTP to this email from Classplus.", parse_mode="HTML")
    await update.message.reply_text("⏳ Waiting for OTP...")

    otp = wait_for_otp(username, domain)
    if otp:
        await update.message.reply_text(f"🔑 OTP received: <code>{otp}</code>\nVerifying...", parse_mode="HTML")
        token = verify_classplus(email, otp)
        if token:
            await update.message.reply_text(f"🎉 Token:\n<code>{token}</code>", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ OTP verification failed.")
    else:
        await update.message.reply_text("❌ OTP not received. Try again.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv)
    print("Bot is running...")
    app.run_polling()
