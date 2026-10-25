"""
Weather bridge for Dynamic Island
Provides current weather + 5-day modern forecast using Open-Meteo.
"""
import sys
import requests
import json
from datetime import datetime
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

WMO_CODES = {
    0: ("☀️", "Despejado"),
    1: ("🌤️", "Mayormente despejado"),
    2: ("⛅", "Parcialmente nublado"),
    3: ("☁️", "Nublado"),
    45: ("🌫️", "Niebla"),
    48: ("🌫️", "Niebla escarchada"),
    51: ("🌦️", "Llovizna leve"),
    53: ("🌦️", "Llovizna moderada"),
    55: ("🌧️", "Llovizna densa"),
    61: ("🌧️", "Lluvia ligera"),
    63: ("🌧️", "Lluvia moderada"),
    65: ("🌧️", "Lluvia torrencial"),
    71: ("🌨️", "Nieve leve"),
    73: ("🌨️", "Nieve moderada"),
    75: ("❄️", "Nieve intensa"),
    80: ("🌦️", "Chubascos breves"),
    81: ("🌧️", "Chubascos moderados"),
    82: ("⛈️", "Tormenta violenta"),
    95: ("⛈️", "Tormenta eléctrica"),
    96: ("⛈️", "Tormenta con granizo"),
    99: ("⛈️", "Tormenta severa")
}

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

def get_weather(lat: float = -32.16145, lon: float = -63.4679, city_name: str = "James Craik, Córdoba") -> Dict[str, Any]:
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,"
        f"apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m&"
        f"daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max&"
        f"timezone=auto"
    )
    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            curr = data.get("current", {})
            daily = data.get("daily", {})
            code = curr.get("weather_code", 0)
            icon, desc = WMO_CODES.get(code, ("⛅", "Variable"))

            # Build 5-day forecast
            forecast = []
            dates = daily.get("time", [])
            codes = daily.get("weather_code", [])
            maxs = daily.get("temperature_2m_max", [])
            mins = daily.get("temperature_2m_min", [])
            rains = daily.get("precipitation_probability_max", [])
            uvs = daily.get("uv_index_max", [])

            for i in range(min(5, len(dates))):
                dt_str = dates[i]
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d")
                    day_label = "Hoy" if i == 0 else f"{DIAS_SEMANA[dt.weekday()]} {dt.day}"
                except Exception:
                    day_label = dt_str
                
                c_code = codes[i] if i < len(codes) else 0
                d_icon, d_desc = WMO_CODES.get(c_code, ("⛅", "Parcial"))

                forecast.append({
                    "day": day_label,
                    "date": dt_str,
                    "icon": d_icon,
                    "desc": d_desc,
                    "max": round(maxs[i]) if i < len(maxs) else "--",
                    "min": round(mins[i]) if i < len(mins) else "--",
                    "rain_prob": rains[i] if i < len(rains) else 0,
                    "uv": round(uvs[i]) if i < len(uvs) else 0
                })

            today_max = forecast[0]["max"] if forecast else round(curr.get("temperature_2m", 20))
            today_min = forecast[0]["min"] if forecast else round(curr.get("temperature_2m", 15))
            today_rain = forecast[0]["rain_prob"] if forecast else 0
            today_uv = forecast[0]["uv"] if forecast else 0

            return {
                "ok": True,
                "city": city_name,
                "temp": round(curr.get("temperature_2m", 20)),
                "feels_like": round(curr.get("apparent_temperature", 20)),
                "humidity": curr.get("relative_humidity_2m", 50),
                "wind": round(curr.get("wind_speed_10m", 0)),
                "icon": icon,
                "desc": desc,
                "max": today_max,
                "min": today_min,
                "rain_prob": today_rain,
                "uv": today_uv,
                "forecast": forecast
            }
    except Exception as e:
        pass
    
    return {
        "ok": False,
        "city": city_name,
        "temp": "--",
        "feels_like": "--",
        "humidity": "--",
        "wind": "--",
        "icon": "⛅",
        "desc": "Clima no disponible",
        "max": "--",
        "min": "--",
        "rain_prob": "--",
        "uv": "--",
        "forecast": []
    }

if __name__ == "__main__":
    w = get_weather()
    print(w["city"], w["temp"], w["desc"])
    for f in w.get("forecast", []):
        print(f["day"], f["icon"], f"Máx: {f['max']}° Mín: {f['min']}° Lluvia: {f['rain_prob']}%")
