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

# Park ID's voor de Live API
PARK_IDS = {
    "EFTELING": 160,
    "PHANTASIALAND": 56,
    "WALIBI_BELGIUM": 14
}

print(f"⚙️ Model laden uit '{MODEL_FILE}'...")
try:
    PIPELINE = joblib.load(MODEL_FILE)
    MODEL = PIPELINE["model"]
    ENCODERS = PIPELINE["encoders"]
    FEATURES = PIPELINE["features"]
    print("✅ Model succesvol geladen!")
except FileNotFoundError:
    print(f"❌ FOUT: Kan '{MODEL_FILE}' niet vinden. Run eerst 'train_model.py'.")
    MODEL = None

# ==============================================================================
# 1. LIVE DATA FUNCTIES
# ==============================================================================

def fetch_live_data(park_name):
    """Haalt actuele wachttijden en OPEN/DICHT status op."""
    park_id = PARK_IDS.get(park_name)
    if not park_id: return {}
    
    url = f"https://queue-times.com/parks/{park_id}/queue_times.json"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200: return {}
        
        data = resp.json()
        live_status = {}
        
        for land in data.get('lands', []):
            for ride in land.get('rides', []):
                live_status[ride['name']] = {
                    "is_open": ride['is_open'],
                    "wait_time": ride['wait_time']
                }
        return live_status
    except Exception as e:
        print(f"⚠️ Kon live data niet ophalen: {e}")
        return {}

# ==============================================================================
# 2. VOORSPEL LOGICA
# ==============================================================================

def get_wait_time_prediction(park_name, ride_name, query_time, live_data_snapshot=None):
    """
    Geeft voorspelling. Als query_time = NU is, gebruiken we live data.
    """
    # 1. Check Live Data Override (Als we binnen 30 min van nu kijken)
    now = datetime.datetime.now()
    minutes_diff = (query_time - now).total_seconds() / 60
    
    if live_data_snapshot and 0 <= minutes_diff < 30:
        if ride_name in live_data_snapshot:
            stat = live_data_snapshot[ride_name]
            # Als de rit gesloten is, return 999 zodat de solver hem vermijdt
            if not stat['is_open']: return 999 
            return stat['wait_time']

    # 2. Anders: ML Model Voorspelling
    meta = ATTRACTION_METADATA.get(ride_name, {})
    if meta.get('park') != park_name: return 0

    # Input voor model bouwen
    row = pd.DataFrame([{
        'attraction_name': ride_name,
        'park_name': park_name,
        'temp_c': 15.0, 'precip_mm': 0.0, 'weather_condition': 'Cloudy', # Fictief weer
        'day_of_week': query_time.isoweekday(),
        'hour_of_day': query_time.hour,
        'is_holiday': is_crowd_risk_day(query_time),
        'type': meta.get('type', 'Unknown'),
        'zone': meta.get('zone', 'Unknown'),
        'capacity': meta.get('capacity', 0),
        'is_indoor': meta.get('is_indoor', 0),
        'hour_sin': np.sin(2 * np.pi * query_time.hour / 24),
        'hour_cos': np.cos(2 * np.pi * query_time.hour / 24),
        'day_sin': np.sin(2 * np.pi * query_time.isoweekday() / 7),
        'day_cos': np.cos(2 * np.pi * query_time.isoweekday() / 7)
    }])

    try:
        def safe_enc(enc, col):
            return row[col].map(lambda x: enc.transform([x])[0] if x in enc.classes_ else 0)
        
        row['park_encoded'] = safe_enc(ENCODERS['park'], 'park_name')
        row['ride_encoded'] = safe_enc(ENCODERS['ride'], 'attraction_name')
        row['type_encoded'] = safe_enc(ENCODERS['type'], 'type')
        row['weather_encoded'] = safe_enc(ENCODERS['weather'], 'weather_condition')
        
        pred = MODEL.predict(row[FEATURES])[0]
        return int(5 * round(max(0, pred) / 5))
    except:
        return 15 # Fallback

# ==============================================================================
# 3. DE SLIMME SOLVER (QueueQuest AI)
# ==============================================================================

def format_time(dt): return dt.strftime('%H:%M')

def solve_route_with_priorities(park_name, must_haves, should_haves, start_str, end_str):
    # Tijd setup
    now = datetime.datetime.now()
    sh, sm = map(int, start_str.split(':'))
    eh, em = map(int, end_str.split(':'))
    current_time = now.replace(hour=sh, minute=sm, second=0)
    park_close = now.replace(hour=eh, minute=em, second=0)
    if current_time < now: current_time += datetime.timedelta(days=1); park_close += datetime.timedelta(days=1)

    # 1. Haal Live Status op
    live_data = fetch_live_data(park_name)
    
    # 2. Filter gesloten attracties
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
    
    # Startpunt
    current_location = "Unknown"
    if park_name == "EFTELING": current_location = "Piraña"
    elif park_name == "PHANTASIALAND": current_location = "Maus au Chocolat"
    elif park_name == "WALIBI_BELGIUM": current_location = "Loup-Garou"

    itinerary = []
    skipped_shoulds = [] 

    while unvisited:
        if current_time >= park_close: break

        best_candidate = None
        best_score = float('inf')
        best_details = {}

        # Beoordeel elke optie
        for ride in unvisited:
            walk_time = get_travel_time(current_location, ride)
            arrival_time = current_time + datetime.timedelta(minutes=walk_time)
            
            if arrival_time >= park_close: continue 

            wait_now = get_wait_time_prediction(park_name, ride, arrival_time, live_data)
            
            # SCORE: Loop + Wacht + Penalty
            cost = walk_time + wait_now
            
            if ride in active_should:
                cost *= 1.5 # Should-haves zijn duurder
            
            if ride in active_must and wait_now < 15:
                cost *= 0.8 # Bonus voor rustige must-haves

            if cost < best_score:
                best_score = cost
                best_candidate = ride
                best_details = {"walk": walk_time, "wait": wait_now, "arrival": arrival_time}

        if not best_candidate: break 

        ride = best_candidate
        meta = ATTRACTION_METADATA.get(ride, {})
        duration = meta.get('duration_min', 5)
        
        finish_time = best_details['arrival'] + datetime.timedelta(minutes=best_details['wait'] + duration)
        
        itinerary.append({
            "ride": ride,
            "type": "MUST" if ride in active_must else "SHOULD",
            "start_walk": format_time(current_time),
            "walk_min": best_details['walk'],
            "arrival_time": format_time(best_details['arrival']),
            "wait_min": best_details['wait'],
            "ride_start": format_time(best_details['arrival'] + datetime.timedelta(minutes=best_details['wait'])),
            "ride_end": format_time(finish_time),
            "note": "⚡ Live Data" if (ride in live_data and abs((current_time - datetime.datetime.now()).total_seconds()) < 3600) else "🔮 Voorspelling"
        })
        
        current_time = finish_time
        current_location = ride
        unvisited.remove(ride)

    return itinerary, closed_rides, unvisited

# ==============================================================================
# 4. DE NAÏEVE SOLVER (Voor Vergelijking)
# ==============================================================================

def solve_naive_route(park_name, wishlist, start_time_str="10:00"):
    """Simuleert de 'domme toerist' die altijd naar de dichtstbijzijnde loopt."""
    now = datetime.datetime.now()
    sh, sm = map(int, start_time_str.split(':'))
    current_time = now.replace(hour=sh, minute=sm, second=0)
    if current_time < now: current_time += datetime.timedelta(days=1)
    
    current_location = "Unknown"
    if park_name == "EFTELING": current_location = "Piraña"
    elif park_name == "PHANTASIALAND": current_location = "Maus au Chocolat"
    elif park_name == "WALIBI_BELGIUM": current_location = "Loup-Garou"

    unvisited = wishlist.copy()
    total_wait = 0
    total_walk = 0
    
    # We gebruiken dezelfde live data logica om eerlijk te vergelijken
    live_data = fetch_live_data(park_name)

    while unvisited:
        # KIES PUUR OP AFSTAND (Dom)
        next_ride = min(unvisited, key=lambda r: get_travel_time(current_location, r))
        
        walk_time = get_travel_time(current_location, next_ride)
        arrival_time = current_time + datetime.timedelta(minutes=walk_time)
        
        # Maar hij moet wel wachten hoe lang de rij DAN is
        wait_time = get_wait_time_prediction(park_name, next_ride, arrival_time, live_data)
        if wait_time == 999: wait_time = 0 # Als dicht, geen wachttijd (maar ook geen pret)
        
        meta = ATTRACTION_METADATA.get(next_ride, {})
        duration = meta.get('duration_min', 5)
        
        total_wait += wait_time
        total_walk += walk_time
        
        current_time = arrival_time + datetime.timedelta(minutes=wait_time + duration)
        current_location = next_ride
        unvisited.remove(next_ride)
        
    return total_wait, total_walk