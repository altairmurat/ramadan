import asyncio
import json
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI
from telethon import TelegramClient, events
from telethon.sessions import StringSession  # optional but recommended

# ── Your custom modules ── (adjust paths/names if needed)
from logger import log_user
from date_time_finder import get_current_time_by_city, get_fajr_time

# ── Logging setup ──
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fajr-bot")

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Optional: use StringSession + env var for persistent session on Render
# SESSION_STRING = os.getenv("TELEGRAM_SESSION_STRING", None)
# client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# For simplicity, using file-based session (will re-auth on each deploy unless you persist the string)
client = TelegramClient("session_bot", API_ID, API_HASH)

app = FastAPI(title="Ramadan Fajr Reminder Bot")

# ── Health endpoint (Render requires this) ──
@app.get("/health")
@app.get("/ping")
async def health_check():
    return {
        "status": "alive",
        "time": datetime.utcnow().isoformat(),
        "bot_running": client.is_connected()
    }

# ── Data file helpers ──
DATA_DIR = "./data"
DATA_FILE = f"{DATA_DIR}/users.json"

def ensure_data_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"users": []}, f, indent=2)

def load_users():
    ensure_data_file()
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Bot states ──
user_states = {}
user_data = {}

@client.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_for_city"
    await event.respond("Hi! I can send you Fajr reminders during Ramadan.\nPlease send me your city name.")

@client.on(events.NewMessage(pattern="/help"))
async def help_handler(event):
    await event.respond(
        "Commands:\n"
        "/start - Set up reminders\n"
        "/time  - Check current time in your city\n"
        "Just send your city → country when prompted."
    )

@client.on(events.NewMessage(pattern="/time"))
async def time_handler(event):
    user_id = event.sender_id
    try:
        data = load_users()
        user_info = next((u for u in data.get("users", []) if u["user_id"] == user_id), None)
        if user_info and "city" in user_info:
            city = user_info["city"]
            current_time = get_current_time_by_city(city)
            await event.respond(f"Current time in {city}: {current_time}")
        else:
            await event.respond("You haven't set your city yet. Use /start to begin.")
    except Exception as e:
        logger.error(f"/time error: {e}")
        await event.respond("Sorry, something went wrong.")

@client.on(events.NewMessage)
async def message_handler(event):
    user_id = event.sender_id
    if event.text.startswith("/"):
        return

    if user_id not in user_states:
        return

    state = user_states[user_id]

    if state == "waiting_for_city":
        city = event.text.strip()
        user_data[user_id] = {"user_id": user_id, "city": city}
        user_states[user_id] = "waiting_for_country"
        await event.respond("Great! Now please send your country name.")

    elif state == "waiting_for_country":
        country = event.text.strip()
        user = user_data[user_id]
        user["country"] = country

        # Save permanently
        data = load_users()
        # Remove old entry if exists
        data["users"] = [u for u in data["users"] if u["user_id"] != user_id]
        data["users"].append(user)
        save_users(data)

        log_user(user_id, user)  # your custom logger

        await event.respond(
            f"✅ Saved!\n"
            f"City: {user['city']}\n"
            f"Country: {country}\n"
            "You will now receive Fajr reminders (during Ramadan)."
        )

        del user_data[user_id]
        del user_states[user_id]

# ── Background reminder checker ──
async def reminder_checker():
    while True:
        try:
            data = load_users()
            for user in data.get("users", []):
                city = user.get("city")
                country = user.get("country")
                user_id = user.get("user_id")

                if not all([city, country, user_id]):
                    continue

                fajr_time = get_fajr_time(city, country)          # e.g. "05:30"
                current_str = get_current_time_by_city(city)      # e.g. "2025-03-01 05:29:45 +03"
                current_time_part = current_str.split(" ")[1][:5] # "05:29"

                if current_time_part == fajr_time:
                    try:
                        await client.send_message(int(user_id), "🌙 It's Fajr time! Time for prayer.")
                        logger.info(f"Fajr reminder sent to {user_id} ({city})")
                    except Exception as send_err:
                        logger.error(f"Failed to send to {user_id}: {send_err}")
        except Exception as e:
            logger.error(f"Reminder loop error: {e}")

        await asyncio.sleep(60)  # check every minute

# ── Bot runner task ──
async def run_telethon_bot():
    try:
        logger.info("Starting Telegram bot authentication...")
        await client.start(bot_token=BOT_TOKEN)
        me = await client.get_me()
        logger.info(f"Bot authenticated successfully → @{me.username} (ID: {me.id})")

        logger.info("Starting reminder checker...")
        asyncio.create_task(reminder_checker())

        logger.info("Running client until disconnected...")
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Telethon critical failure: {e}", exc_info=True)

# ── FastAPI lifespan (modern way - Python 3.11+ friendly) ──
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(run_telethon_bot())

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Shutting down Telethon client...")
    await client.disconnect()

# ── Main entry point ──
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",               # change "main" to your actual filename without .py
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
