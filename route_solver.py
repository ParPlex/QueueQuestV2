import pandas as pd
import numpy as np
import datetime
import requests
import joblib
import pytz
import streamlit as st  # Nodig voor Caching
from copy import deepcopy

# --- 0. CONFIGURATIE & IMPORTS ---
MODEL_FILE = "queuequest_model.pkl"
PARK_IDS = {"EFTELING": 160, "PHANTASIALAND": 56, "WALIBI_BELGIUM": 14}

# Probeer helpers te laden
try:
    from queuequest_meta import ATTRACTION_METADATA
    from holiday_utils import is_crowd_risk_day
    from distance_utils import get_travel_time
except ImportError:
    ATTRACTION_METADATA = {}
    def is_crowd_risk_day(date): return False
    def get_travel_time(start, end): return 10

# API Mappings
API_NAME_MAPPING = {
    "Fairytale Forest": "Sprookjesbos", "The Six Swans": "De Zes Zwanen",
    "Stoomtrein Marerijk": "Stoomtrein", "Stoomtrein Ruigrijk": "Stoomtrein",
    "Max & Moritz": "Max & Moritz", "Symbolica: Paleis der Fantasie": "Symbolica", 
    "Black Mamba ": "Black Mamba", "Taron ": "Taron",
    "Cobra": "Cobra", "Pulsar": "Pulsar"
}

# Phantasialand Loopmatrix
PHL_LOCATIONS = {
    "Ingang": "Berlin", "Maus au Chocolat": "Berlin",
    "Taron": "Klugheim", "Raik": "Klugheim",
    "River Quest": "Mystery", "Mystery Castle": "Mystery",
    "F.L.Y.": "Rookburgh", "Black Mamba": "Africa", "Deep in Africa": "Africa",
    "Talocan": "Mexico", "Chiapas": "Mexico", "Colorado Adventure": "Mexico",
    "Winja's Fear": "Wuze Town", "Winja's Force": "Wuze Town", "Crazy Bats": "Wuze Town",
    "Feng Ju Palace": "China", "Geister Rikscha": "China"
}

PHL_WALK_MATRIX = {
    ("Berlin", "Rookburgh"): 2, ("Berlin", "Mexico"): 5, ("Berlin", "China"): 8, 
    ("Berlin", "Klugheim"): 6, ("Berlin", "Africa"): 8, ("Klugheim", "Mexico"): 3,
    ("Klugheim", "China"): 4, ("Klugheim", "Africa"): 4, ("Klugheim", "Rookburgh"): 8, 
    ("Mexico", "Africa"): 3, ("Rookburgh", "Wuze Town"): 6
}

# --- 1. MODEL LADEN (GEOPTIMALISEERD MET CACHING) ---
MODEL = None
ENCODERS = None
FEATURES = None

@st.cache_resource(show_spinner=False)
def load_model_pipeline():
    print(f"📥 Proberen model te laden: {MODEL_FILE}...")
    return joblib.load(MODEL_FILE)

try:
    PIPELINE = load_model_pipeline()
    MODEL = PIPELINE["model"]
    ENCODERS = PIPELINE["encoders"]
    FEATURES = PIPELINE["features"]
except Exception as e:
    print(f"⚠️ WAARSCHUWING: Model niet geladen. Fallback naar heuristiek. Fout: {e}")
    MODEL = None

# --- 2. DATA FETCHING (GEOPTIMALISEERD MET CACHING) ---
@st.cache_data(ttl=300, show_spinner=False)
def fetch_live_data(park_name):
    park_id = PARK_IDS.get(park_name)
    if not park_id: return {}
    headers = {'User-Agent': 'Mozilla/5.0 (QueueQuestBot/2.0)', 'Accept': 'application/json'}
    try:
        resp = requests.get(f"https://queue-times.com/parks/{park_id}/queue_times.json", headers=headers, timeout=5)
        if resp.status_code != 200: return {}
        data = resp.json()
        live = {}
        for land in data.get('lands', []):
            for ride in land.get('rides', []):
                raw_name = ride['name'].strip()
                clean_name = API_NAME_MAPPING.get(raw_name, raw_name)
                final_name = clean_name
                if clean_name not in ATTRACTION_METADATA and raw_name in ATTRACTION_METADATA:
                    final_name = raw_name
                wait = ride.get('wait_time', 0)
                live[final_name] = {"is_open": ride['is_open'], "wait_time": wait if wait is not None else 0}
        return live
    except Exception as e:
        print(f"❌ API Fout: {e}")
        return {}

# --- 3. TRANSIT & UTILS (MET PACE FACTOR) ---
def calculate_transit_time(park, start, end, pace=1.0):
    base_time = 10 
    if start == end: 
        base_time = 0
    elif start == "Unknown" or end == "Unknown": 
        base_time = 10
    elif park == "PHANTASIALAND":
        zone_a = PHL_LOCATIONS.get(start, "Berlin")
        zone_b = PHL_LOCATIONS.get(end, "Berlin")
        if zone_a == zone_b: 
            base_time = 4
        else:
            pair = tuple(sorted((zone_a, zone_b)))
            found = False
            for k, v in PHL_WALK_MATRIX.items():
                if set(k) == set(pair): 
                    base_time = v
                    found = True
                    break
            if not found: base_time = 12
    else:
        base_time = get_travel_time(start, end)
    return int(base_time * pace)

def format_time(dt): return dt.strftime('%H:%M')

# --- 4. PREDICTIE ENGINE ---
def get_wait_time_prediction(park_name, ride_name, query_time, live_data_snapshot=None, weather_override=None):
    tz = query_time.tzinfo
    now = datetime.datetime.now(tz) if tz else datetime.datetime.now()
    minutes_delta = (query_time - now).total_seconds() / 60
    
    if not weather_override and live_data_snapshot and 0 <= minutes_delta < 30:
        if ride_name in live_data_snapshot:
            data = live_data_snapshot[ride_name]
            if not data['is_open']: return 999 
            return data['wait_time']

    if MODEL:
        try:
            meta = ATTRACTION_METADATA.get(ride_name, {})
            w_temp, w_precip, w_cond = (weather_override.get('temp_c', 15.0), weather_override.get('precip_mm', 0.0), weather_override.get('condition', 'Cloudy')) if weather_override else (15.0, 0.0, 'Cloudy')
            input_data = {
                'attraction_name': ride_name, 'park_name': park_name,
                'temp_c': w_temp, 'precip_mm': w_precip, 'weather_condition': w_cond,
                'day_of_week': query_time.isoweekday(), 'hour_of_day': query_time.hour,
                'is_holiday': is_crowd_risk_day(query_time),
                'type': meta.get('type', 'Unknown'), 'zone': meta.get('zone', 'Unknown'),
                'capacity': meta.get('capacity', 1000), 'is_indoor': meta.get('is_indoor', 0),
                'hour_sin': np.sin(2 * np.pi * query_time.hour / 24), 'hour_cos': np.cos(2 * np.pi * query_time.hour / 24),
                'day_sin': np.sin(2 * np.pi * query_time.isoweekday() / 7), 'day_cos': np.cos(2 * np.pi * query_time.isoweekday() / 7)
            }
            row = pd.DataFrame([input_data])
            def safe_transform(enc, val):
                try: return enc.transform([val])[0] if val in enc.classes_ else 0
                except: return 0
            if ENCODERS:
                row['park_encoded'] = safe_transform(ENCODERS.get('park'), park_name)
                row['ride_encoded'] = safe_transform(ENCODERS.get('ride'), ride_name)
                row['type_encoded'] = safe_transform(ENCODERS.get('type'), row['type'][0])
                row['weather_encoded'] = safe_transform(ENCODERS.get('weather'), w_cond)
            final_input = row[FEATURES] if FEATURES else row
            pred = MODEL.predict(final_input)[0]
            return int(5 * round(max(0, pred) / 5))
        except: pass
    return 10 if 11 <= query_time.hour <= 16 else 10 + 25

# --- 5. SCORE CALCULATOR ---
def calculate_dynamic_score(park_name, candidate, current_loc, arrival_time, live_data, pace=1.0):
    transit = calculate_transit_time(park_name, current_loc, candidate, pace)
    wait_at_arrival = get_wait_time_prediction(park_name, candidate, arrival_time, live_data)
    if wait_at_arrival >= 999: return float('inf'), transit, wait_at_arrival
    future_time = arrival_time + datetime.timedelta(hours=2)
    wait_in_future = get_wait_time_prediction(park_name, candidate, future_time, live_data)
    urgency_bonus = -20 if wait_in_future > (wait_at_arrival + 15) else (15 if wait_in_future < (wait_at_arrival - 10) else 0)
    total_score = max(transit, transit + wait_at_arrival + urgency_bonus)
    return total_score, transit, wait_at_arrival

# --- 6. MAX SCORE SOLVER (MET ANTI-REPETITIE) ---
def solve_max_score_route(park_name, start_str, end_str, start_location="Ingang", pace_factor=1.0):
    if start_str is None: start_str = "10:00"
    tz = pytz.timezone('Europe/Brussels')
    now = datetime.datetime.now(tz)
    sh, sm = map(int, start_str.split(':'))
    eh, em = map(int, end_str.split(':'))
    current_time = tz.localize(datetime.datetime.combine(now.date(), datetime.time(sh, sm)))
    park_close = tz.localize(datetime.datetime.combine(now.date(), datetime.time(eh, em)))
    if (now - current_time).total_seconds() > 6 * 3600:
        current_time += datetime.timedelta(days=1)
        park_close += datetime.timedelta(days=1)
    if park_close <= current_time: park_close += datetime.timedelta(days=1)

    is_simulating_now = (abs((current_time - now).total_seconds()) < 3600)
    live_data = fetch_live_data(park_name) if is_simulating_now else {}
    candidates = [r for r, m in ATTRACTION_METADATA.items() if m.get('park') == park_name and m.get('score', 0) > 0 and m.get('type') not in ['Restaurant', 'Snack']]
    if is_simulating_now and live_data:
        candidates = [c for c in candidates if live_data.get(c, {}).get('is_open', True)]

    itinerary = []
    current_loc = start_location if start_location != "Unknown" else "Ingang"
    ride_counts = {c: 0 for c in candidates}

    while current_time < park_close:
        best_cand, best_roi, best_det = None, -1, {}
        last_ride = itinerary[-1]['ride'] if itinerary else None

        for cand in candidates:
            transit = calculate_transit_time(park_name, current_loc, cand, pace_factor)
            arrival = current_time + datetime.timedelta(minutes=transit)
            if arrival >= park_close: continue
            wait = get_wait_time_prediction(park_name, cand, arrival, live_data)
            if wait >= 999: continue
            
            # --- ANTI-REPETITIE LOGICA ---
            ride_quality = ATTRACTION_METADATA[cand].get('score', 5)
            if cand == last_ride and ride_quality < 7:
                continue # Skip als score < 7 en herhaling

            duration = ATTRACTION_METADATA[cand].get('duration_min', 5)
            cost_minutes = max(5, transit + wait + duration)
            decay = 0.7 ** ride_counts[cand] 
            roi = (ride_quality * decay) / cost_minutes

            if roi > best_roi:
                best_roi, best_cand, best_det = roi, cand, {"transit": transit, "wait": wait, "arrival": arrival, "duration": duration}

        if not best_cand: break
        ride_start = best_det['arrival'] + datetime.timedelta(minutes=best_det['wait'])
        ride_end = ride_start + datetime.timedelta(minutes=best_det['duration'])
        itinerary.append({
            "ride": best_cand, "type": "SCORE", "start_walk": format_time(current_time), 
            "walk_min": int(best_det['transit']), "arrival_time": format_time(best_det['arrival']), 
            "wait_min": int(best_det['wait']), "ride_start": format_time(ride_start), 
            "ride_end": format_time(ride_end), "note": f"Rit #{ride_counts[best_cand] + 1}"
        })
        current_time, current_loc = ride_end, best_cand
        ride_counts[best_cand] += 1
    return itinerary, [], []

# --- 7. STANDAARD SOLVER (MET ANTI-REPETITIE) ---
def solve_route_with_priorities(park_name, must_haves, should_haves, start_str, end_str, start_location="Unknown", lunch_config=None, pace_factor=1.0):
    if start_str is None: start_str = "10:00"
    tz = pytz.timezone('Europe/Brussels')
    now = datetime.datetime.now(tz)
    sh, sm = map(int, start_str.split(':'))
    eh, em = map(int, end_str.split(':'))
    current_time = tz.localize(datetime.datetime.combine(now.date(), datetime.time(sh, sm)))
    park_close = tz.localize(datetime.datetime.combine(now.date(), datetime.time(eh, em)))
    if (now - current_time).total_seconds() > 6 * 3600:
        current_time += datetime.timedelta(days=1)
        park_close += datetime.timedelta(days=1)
    if park_close <= current_time: park_close += datetime.timedelta(days=1)

    is_simulating_now = (abs((current_time - now).total_seconds()) < 3600)
    live_data = fetch_live_data(park_name) if is_simulating_now else {}
    
    lunch_done = False
    lunch_dt = tz.localize(datetime.datetime.combine(current_time.date(), lunch_config['time'])) if lunch_config else None
    unvisited = list(set(must_haves + should_haves))
    closed_rides = []
    
    if is_simulating_now and live_data:
        for ride in list(unvisited):
            if ride in live_data and not live_data[ride]['is_open']:
                closed_rides.append(ride); unvisited.remove(ride)

    itinerary, current_loc, skipped = [], start_location, []
    if current_loc in ["Unknown", "Ingang"]:
        current_loc = "Maus au Chocolat" if park_name == "PHANTASIALAND" else ("Fabula" if park_name == "EFTELING" else "Loup-Garou")

    while unvisited:
        if current_time >= park_close: skipped = list(unvisited); break
        if lunch_config and not lunch_done and current_time >= lunch_dt:
            rest = lunch_config['restaurant']
            walk = calculate_transit_time(park_name, current_loc, rest, pace_factor)
            arr = current_time + datetime.timedelta(minutes=walk)
            fin = arr + datetime.timedelta(minutes=lunch_config['duration'])
            itinerary.append({"ride": f"🍽️ Lunch: {rest}", "type": "LUNCH", "start_walk": format_time(current_time), "walk_min": int(walk), "arrival_time": format_time(arr), "wait_min": 0, "ride_start": format_time(arr), "ride_end": format_time(fin), "note": "Pauze"})
            current_time, current_loc, lunch_done = fin, rest, True; continue

        best_cand, best_score, best_det = None, float('inf'), {}
        last_ride = itinerary[-1]['ride'] if itinerary and itinerary[-1]['type'] != 'LUNCH' else None

        for candidate in unvisited:
            temp_transit = calculate_transit_time(park_name, current_loc, candidate, pace_factor)
            temp_arrival = current_time + datetime.timedelta(minutes=temp_transit)
            if temp_arrival >= park_close: continue
            score, transit, wait = calculate_dynamic_score(park_name, candidate, current_loc, temp_arrival, live_data, pace_factor)
            
            # --- ANTI-REPETITIE LOGICA ---
            ride_quality = ATTRACTION_METADATA.get(candidate, {}).get('score', 5)
            if candidate == last_ride:
                if ride_quality < 7: score += 500 # Penalty voor lage kwaliteit herhaling
                else: score += 20 # Kleine drempel voor hoge kwaliteit herhaling

            if candidate in should_haves: score *= 1.3 
            if score < best_score:
                best_score, best_cand, best_det = score, candidate, {"transit": transit, "wait": wait, "arrival": temp_arrival}

        if not best_cand: skipped = list(unvisited); break 
        dur = ATTRACTION_METADATA.get(best_cand, {}).get('duration_min', 5)
        ride_start = best_det['arrival'] + datetime.timedelta(minutes=best_det['wait'])
        ride_end = ride_start + datetime.timedelta(minutes=dur)
        itinerary.append({"ride": best_cand, "type": "MUST" if best_cand in must_haves else "SHOULD", "start_walk": format_time(current_time), "walk_min": int(best_det['transit']), "arrival_time": format_time(best_det['arrival']), "wait_min": int(best_det['wait']), "ride_start": format_time(ride_start), "ride_end": format_time(ride_end), "note": "⚡ Live" if is_simulating_now else "🔮 Forecast"})
        current_time, current_loc = ride_end, best_cand
        unvisited.remove(best_cand)

    return itinerary, closed_rides, skipped