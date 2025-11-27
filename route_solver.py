import joblib
import pandas as pd
import numpy as np
import datetime
import requests
from queuequest_meta import ATTRACTION_METADATA
from holiday_utils import is_crowd_risk_day
from distance_utils import get_travel_time

# --- CONFIGURATIE & MODEL LADEN ---
MODEL_FILE = "queuequest_model.pkl"

PARK_IDS = {"EFTELING": 160, "PHANTASIALAND": 56, "WALIBI_BELGIUM": 14}

try:
    PIPELINE = joblib.load(MODEL_FILE)
    MODEL = PIPELINE["model"]
    ENCODERS = PIPELINE["encoders"]
    FEATURES = PIPELINE["features"]
except:
    MODEL = None

# 1. LIVE DATA
def fetch_live_data(park_name):
    park_id = PARK_IDS.get(park_name)
    if not park_id: return {}
    try:
        resp = requests.get(f"https://queue-times.com/parks/{park_id}/queue_times.json", timeout=5)
        if resp.status_code != 200: return {}
        data = resp.json()
        live_status = {}
        for land in data.get('lands', []):
            for ride in land.get('rides', []):
                live_status[ride['name']] = {"is_open": ride['is_open'], "wait_time": ride['wait_time']}
        return live_status
    except: return {}

# 2. VOORSPEL LOGICA
def get_wait_time_prediction(park_name, ride_name, query_time, live_data_snapshot=None):
    now = datetime.datetime.now()
    minutes_diff = (query_time - now).total_seconds() / 60
    
    # Live override (eerste 30 min)
    if live_data_snapshot and 0 <= minutes_diff < 30:
        if ride_name in live_data_snapshot:
            stat = live_data_snapshot[ride_name]
            if not stat['is_open']: return 999 
            return stat['wait_time']

    # AI Model
    meta = ATTRACTION_METADATA.get(ride_name, {})
    if meta.get('park') != park_name: return 0

    row = pd.DataFrame([{
        'attraction_name': ride_name, 'park_name': park_name,
        'temp_c': 15.0, 'precip_mm': 0.0, 'weather_condition': 'Cloudy',
        'day_of_week': query_time.isoweekday(), 'hour_of_day': query_time.hour,
        'is_holiday': is_crowd_risk_day(query_time),
        'type': meta.get('type', 'Unknown'), 'zone': meta.get('zone', 'Unknown'),
        'capacity': meta.get('capacity', 0), 'is_indoor': meta.get('is_indoor', 0),
        'hour_sin': np.sin(2 * np.pi * query_time.hour / 24),
        'hour_cos': np.cos(2 * np.pi * query_time.hour / 24),
        'day_sin': np.sin(2 * np.pi * query_time.isoweekday() / 7),
        'day_cos': np.cos(2 * np.pi * query_time.isoweekday() / 7)
    }])

    try:
        def safe_enc(enc, col): return row[col].map(lambda x: enc.transform([x])[0] if x in enc.classes_ else 0)
        row['park_encoded'] = safe_enc(ENCODERS['park'], 'park_name')
        row['ride_encoded'] = safe_enc(ENCODERS['ride'], 'attraction_name')
        row['type_encoded'] = safe_enc(ENCODERS['type'], 'type')
        row['weather_encoded'] = safe_enc(ENCODERS['weather'], 'weather_condition')
        pred = MODEL.predict(row[FEATURES])[0]
        return int(5 * round(max(0, pred) / 5))
    except: return 15

# 3. SOLVER (Nu met start_location!)
def format_time(dt): return dt.strftime('%H:%M')

def solve_route_with_priorities(park_name, must_haves, should_haves, start_str, end_str, start_location="Unknown"):
    now = datetime.datetime.now()
    sh, sm = map(int, start_str.split(':'))
    eh, em = map(int, end_str.split(':'))
    current_time = now.replace(hour=sh, minute=sm, second=0)
    park_close = now.replace(hour=eh, minute=em, second=0)
    
    if current_time < now and (now - current_time).total_seconds() > 3600: 
        current_time += datetime.timedelta(days=1)
        park_close += datetime.timedelta(days=1)

    live_data = fetch_live_data(park_name)
    
    active_must = []
    active_should = []
    closed_rides = []

    for ride in must_haves + should_haves:
        if ride in live_data and not live_data[ride]['is_open']:
            closed_rides.append(ride)
            continue
        if ride in must_haves: active_must.append(ride)
        else: active_should.append(ride)

    unvisited = active_must + active_should
    
    # Gebruik opgegeven startlocatie of default
    current_location = start_location
    if current_location == "Unknown" or current_location == "Ingang":
        if park_name == "EFTELING": current_location = "Piraña"
        elif park_name == "PHANTASIALAND": current_location = "Maus au Chocolat"
        elif park_name == "WALIBI_BELGIUM": current_location = "Loup-Garou"

    itinerary = []
    
    while unvisited:
        if current_time >= park_close: break

        best_candidate = None
        best_score = float('inf')
        best_details = {}

        for ride in unvisited:
            walk_time = get_travel_time(current_location, ride)
            arrival_time = current_time + datetime.timedelta(minutes=walk_time)
            
            if arrival_time >= park_close: continue 

            wait_now = get_wait_time_prediction(park_name, ride, arrival_time, live_data)
            
            # Slimme Score: Lopen + Wachten
            cost = walk_time + wait_now
            
            if ride in active_should: cost *= 1.5
            if ride in active_must and wait_now < 15: cost *= 0.8

            if cost < best_score:
                best_score = cost
                best_candidate = ride
                best_details = {"walk": walk_time, "wait": wait_now, "arrival": arrival_time}

        if not best_candidate: break 

        ride = best_candidate
        meta = ATTRACTION_METADATA.get(ride, {})
        duration = meta.get('duration_min', 5)
        
        finish_time = best_details['arrival'] + datetime.timedelta(minutes=best_details['wait'] + duration)
        
        is_live = (ride in live_data and abs((current_time - datetime.datetime.now()).total_seconds()) < 3600)
        
        itinerary.append({
            "ride": ride,
            "type": "MUST" if ride in active_must else "SHOULD",
            "start_walk": format_time(current_time),
            "walk_min": best_details['walk'],
            "arrival_time": format_time(best_details['arrival']),
            "wait_min": best_details['wait'],
            "ride_start": format_time(best_details['arrival'] + datetime.timedelta(minutes=best_details['wait'])),
            "ride_end": format_time(finish_time),
            "note": "⚡ Live" if is_live else "🔮 Forecast"
        })
        
        current_time = finish_time
        current_location = ride
        unvisited.remove(ride)

    return itinerary, closed_rides, unvisited

# 4. NAÏEVE SOLVER (Nodig voor app.py import, mag leeg blijven of simpel)
def solve_naive_route(park_name, wishlist, start_time_str="10:00"):
    # Simpele return voor nu om de app niet te laten crashen
    return 0, 0
