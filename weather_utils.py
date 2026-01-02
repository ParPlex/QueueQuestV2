import requests
import datetime

# Coördinaten van de parken (Centraal punt)
PARK_COORDS = {
    "EFTELING": {"lat": 51.6500, "lon": 5.0470},
    "PHANTASIALAND": {"lat": 50.8000, "lon": 6.8800},
    "WALIBI_BELGIUM": {"lat": 50.7000, "lon": 4.5900}
}

# Klimaatgemiddelden (Maand 1-12) voor Fallback (>14 dagen)
# [Temp Max, Neerslagkans %]
CLIMATE_AVERAGES = {
    1: [6, 40], 2: [7, 35], 3: [10, 30], 4: [14, 25],
    5: [18, 20], 6: [21, 20], 7: [23, 20], 8: [23, 20],
    9: [19, 25], 10: [15, 30], 11: [10, 40], 12: [7, 45]
}

def get_automated_weather(park_name, target_date):
    """
    Haalt het weer op.
    - Binnen 14 dagen: Live API (Open-Meteo).
    - Verder weg: Statistisch gemiddelde.
    """
    coords = PARK_COORDS.get(park_name, PARK_COORDS["EFTELING"])
    today = datetime.date.today()
    days_diff = (target_date - today).days

    # SCENARIO A: HISTORISCH / VER IN TOEKOMST (> 14 dagen)
    if days_diff > 14 or days_diff < 0:
        avg = CLIMATE_AVERAGES.get(target_date.month, [15, 20])
        return {
            "temp_c": avg[0],
            "precip_mm": 0.0 if avg[1] < 30 else 2.0, # Simpel: als kans hoog is, rekenen we met regen
            "rain_prob": avg[1],
            "source": "📊 Historisch Gemiddelde (Lange termijn)"
        }

    # SCENARIO B: LIVE VOORSPELLING (0 - 14 dagen)
    try:
        # Open-Meteo API (Gratis, geen key nodig)
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&daily=temperature_2m_max,precipitation_sum,precipitation_probability_max&timezone=auto"
        resp = requests.get(url, timeout=2)
        data = resp.json()
        
        # Zoek de juiste dag in de response
        daily = data.get('daily', {})
        dates = daily.get('time', [])
        target_str = target_date.strftime('%Y-%m-%d')
        
        if target_str in dates:
            idx = dates.index(target_str)
            temp = daily['temperature_2m_max'][idx]
            rain_mm = daily['precipitation_sum'][idx]
            rain_prob = daily['precipitation_probability_max'][idx]
            
            return {
                "temp_c": temp,
                "precip_mm": rain_mm,
                "rain_prob": rain_prob,
                "source": "🛰️ Live Weersvoorspelling"
            }
    except Exception as e:
        print(f"Weer API Fout: {e}")
    
    # Fallback als API faalt
    return {"temp_c": 15, "precip_mm": 0.0, "rain_prob": 10, "source": "⚠️ Fallback (Standaard)"}