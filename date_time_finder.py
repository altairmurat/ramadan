from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from datetime import datetime
import requests

url = "http://api.aladhan.com/v1/timingsByCity"

def get_current_time_by_city(city_name):
    geolocator = Nominatim(user_agent="city_time_app")
    try:
        location = geolocator.geocode(city_name)
        if location:
            tf = TimezoneFinder()
            timezone_str = tf.timezone_at(lng=location.longitude, lat=location.latitude)
            if timezone_str:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(timezone_str)
                current_time = datetime.now(tz)
                return current_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                return f"Не удалось определить часовой пояс для {city_name}."
        else:
            return f"Не удалось найти местоположение для {city_name}."
    except Exception as e:
        return f"Произошла ошибка: {e}"
    
def get_fajr_time(city, country):
    date_time = get_current_time_by_city(city)
    date = datetime.strptime(date_time, '%Y-%m-%d %H:%M:%S').strftime("%d-%m-%Y")
    url_withdate = f"http://api.aladhan.com/v1/timingsByCity/{date}"
    params = {
        "city": city,
        "country": country,
        "method": 2
    }
    response = requests.get(url_withdate, params=params).json()
    return response['data']['timings']['Fajr']