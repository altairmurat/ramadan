import json
from datetime import date, datetime
import requests

def log_user(user_id, city_country):
    try:
        with open('./data/users.json', 'r') as fr:
            data = json.load(fr)
    except json.JSONDecodeError:
        data = {"users": []}
    except FileNotFoundError:
        data = {"users": []}
    
    city_country["user_id"] = user_id
    data["users"].append(city_country)
    
    with open('./data/users.json', 'w') as fw:
        json.dump(data, fw, indent=4)
    print("user registered successfully")
