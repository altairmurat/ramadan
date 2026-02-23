import asyncio
import json
import os
import time
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI
from telethon import TelegramClient, events
from telethon.sessions import StringSession  # optional but safer

# Your custom modules (make sure they exist in the repo)
from logger import log_user
from date_time_finder import get_current_time_by_city, get_fajr_time

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Use StringSession if you want to avoid file-based session on ephemeral filesystem
# Otherwise keep "session_bot" (but Render free may lose the file on restart)
client = TelegramClient("session_bot", api_id, api_hash).start(bot_token=bot_token)

app = FastAPI(title="Ramadan Fajr Reminder Bot")

# ── Health endpoint for Render (required for Web Service) ─────────────────────
@app.get("/health")
@app.get("/ping")
async def health_check():
    return {
        "status": "alive",
        "time": datetime.utcnow().isoformat(),
        "bot_running": client.is_connected()
    }

# ── Bot handlers ──────────────────────────────────────────────────────────────
user_states = {}
user_data = {}

@client.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_for_city"
    await event.respond("Hi, I can schedule Ramadan reminders\nSend me your city.")

@client.on(events.NewMessage(pattern="/help"))
async def help_handler(event):
    await event.respond(
        "To set up reminders, use /start and follow the instructions.\n"
        "To check current time in your city: /time"
    )

@client.on(events.NewMessage(pattern="/time"))
async def time_handler(event):
    user_id = event.sender_id
    try:
        with open('./data/users.json', 'r') as f:
            data = json.load(f)
        
        user_info = next((u for u in data.get("users", []) if u["user_id"] == user_id), None)
        
        if user_info:
            city = user_info["city"]
            current_time = get_current_time_by_city(city)
            await event.respond(f"The current time in {city} is: {current_time}")
        else:
            await event.respond("You haven't set your city yet. Use /start to set it up.")
    except Exception as e:
        await event.respond("Sorry, something went wrong reading user data.")
        print(f"/time error: {e}")

@client.on(events.NewMessage)
async def message_handler(event):
    user_id = event.sender_id
    
    if event.text.startswith("/"):
        return  # ignore other commands
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == "waiting_for_city":
        city = event.text.strip()
        user_data[user_id] = {"user_id": user_id, "city": city}
        user_states[user_id] = "waiting_for_country"
        await event.respond("Great! Now send me your country.")
    
    elif state == "waiting_for_country":
        country = event.text.strip()
        user_data[user_id]["country"] = country
        user_states[user_id] = "completed"
        
        await event.respond("Great! Just a sec, saving your data...")
        
        log_user(user_id, user_data[user_id])
        
        await event.respond(
            f"Saved ✅\nCity: {user_data[user_id]['city']}\nCountry: {country}"
        )
        
        # Optional: clean up temp data
        del user_data[user_id]
        del user_states[user_id]

# ── Reminder background task ──────────────────────────────────────────────────
async def reminder_checker():
    while True:
        try:
            with open('./data/users.json', 'r') as f:
                data = json.load(f)
            
            for user in data.get("users", []):
                city = user.get("city")
                country = user.get("country")
                user_id = user.get("user_id")
                
                if not all([city, country, user_id]):
                    continue
                
                fajr_time = get_fajr_time(city, country)           # expect "05:30"
                current_str = get_current_time_by_city(city)       # e.g. "2026-02-23 05:29:45 +03"
                current_time_part = current_str.split(" ")[1][:5]  # "05:29"
                
                if current_time_part == fajr_time:
                    try:
                        await client.send_message(int(user_id), "It's time for Fajr prayer! 🌙")
                        print(f"Fajr sent to {user_id} in {city}")
                    except Exception as send_err:
                        print(f"Failed to send to {user_id}: {send_err}")
        except Exception as e:
            print(f"Reminder loop error: {e}")
        
        await asyncio.sleep(60)  # check every minute

# ── Main startup ──────────────────────────────────────────────────────────────
async def startup():
    try:
        await client.start(bot_token=BOT_TOKEN)
        print("Bot successfully started and authenticated")
        
        # Start reminder checker as background task
        asyncio.create_task(reminder_checker())
        
        print("Reminder checker task started")
    except Exception as e:
        print(f"Startup failed: {e}")
        raise

# ── Run everything together ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    
    # Run startup tasks
    loop = asyncio.get_event_loop()
    loop.run_until_complete(startup())
    
    # Then start the web server (Render needs this)
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        # workers=1  # keep single worker on free tier
    )


