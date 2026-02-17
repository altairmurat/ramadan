from telethon import TelegramClient, events
import asyncio
from telethon.tl.types import SendMessageTypingAction
from openai_helper.gpt_listener import ask_gpt
import json
import time
from logger import log_user
from date_time_finder import get_current_time_by_city, get_fajr_time
from dotenv import load_dotenv
import os
from fastapi import FastAPI

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"status": "active"}

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

client = TelegramClient("session_bot", api_id, api_hash).start(bot_token=bot_token)

user_states = {}
user_data = {}

@client.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_for_city"
    await event.respond("Hi, I can schedule Ramadan reminders \nSend me your city.")

@client.on(events.NewMessage(pattern="/launch"))
async def launch_handler(event):
    await event.respond("Launching the reminder system...")
    while True:
        with open('./data/users.json', 'r') as fr:
            data = json.load(fr)
        
        for user in data["users"]:
            city = user["city"]
            country = user["country"]
            fajr_time = get_fajr_time(city, country)
            current_time = get_current_time_by_city(city)
            
            if current_time.split(" ")[1][:5] == fajr_time:
                await client.send_message(user["user_id"], "It's time for Fajr prayer! 🌙")
        
        time.sleep(60)  # Check every minute
        
@client.on(events.NewMessage(pattern="/help"))
async def help_handler(event):
    await event.respond("To set up reminders, \nuse /start and follow the instructions. \nTo launch the reminder system, use /launch. \n/time to check current time in your city.")
    
@client.on(events.NewMessage(pattern="/time"))
async def time_handler(event):
    user_id = event.sender_id
    with open('./data/users.json', 'r') as fr:
        data = json.load(fr)
    
    user_info = next((user for user in data["users"] if user["user_id"] == user_id), None)
    
    if user_info:
        city = user_info["city"]
        current_time = get_current_time_by_city(city)
        await event.respond(f"The current time in {city} is: {current_time}")
    else:
        await event.respond("You haven't set your city yet. Use /start to set it up.")

@client.on(events.NewMessage)
async def message_handler(event):
    user_id = event.sender_id
    
    # Ignore commands
    if event.text.startswith("/"):
        return

    # Check user state
    if user_id in user_states:
        
        # Step 1: Waiting for city
        if user_states[user_id] == "waiting_for_city":
            city = event.text.strip()
            
            user_data[user_id] = {"user_id": user_id, "city": city}
            user_states[user_id] = "waiting_for_country"
            
            await event.respond("Great! Now send me your country.")

        # Step 2: Waiting for country
        elif user_states[user_id] == "waiting_for_country":
            country = event.text.strip()
            
            user_data[user_id]["country"] = country
            user_states[user_id] = "completed"
            
            await event.respond("Great! Just a sec, saving your data...")
        
            log_user(user_id, user_data[user_id])
            
            await event.respond(
                f"Saved ✅\nCity: {user_data[user_id]['city']}\nCountry: {country}"
            )
            
            


client.run_until_disconnected()
