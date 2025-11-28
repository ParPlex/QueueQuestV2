import pandas as pd
import numpy as np
import datetime
import requests
import joblib
import pytz

# Probeer interne modules te laden, anders fallbacks
try:
    from queuequest_meta import ATTRACTION_METADATA
    from holiday_utils import is_crowd_risk_day
    from distance_utils import get_travel_time
except ImportError:
    ATTRACTION_METADATA = {}
    def is_crowd_risk_day(date): return False
    def get_travel_time(start, end): return 10

# --- 1. CONFIGURATIE & MAPPINGS ---
MODEL_FILE = "queuequest_model.pkl"
PARK_IDS = {"EFTELING": 160, "PHANTASIALAND": 56, "WALIBI_BELGIUM": 14}

# Mapping: Links = API naam, Rechts = App naam
API_NAME_MAPPING = {
    # EFTELING
    "Fairytale Forest": "Sprookjesbos",
    "The Six Swans": "De Zes Zwanen",
    "Stoomtrein Marerijk": "Stoomtrein",
    "Stoomtrein Ruigrijk": "Stoomtrein",
    "Max & Moritz": "Max & Moritz",
    "Symbolica: Paleis der Fantasie": "Symbolica", 
    
    # PHANTASIALAND
    "Black Mamba ": "Black Mamba",
    "Taron ": "Taron",
    
    # WALIBI
    "Cobra": "Cobra",
    "Pulsar": "Pulsar"
}

# Phantasialand Loopmatrix
PHL_LOCATIONS = {
    "Ingang": "Berlin", "Maus au Chocolat": "Berlin",
    "Taron": "Klugheim", "Raik": "Klugheim",
    "River Quest": "Mystery", "Mystery Castle": "Mystery",
    "F.L.Y.": "Rookburgh",
    "Black Mamba": "Africa", "Deep in Africa": "Africa",
    "Talocan": "Mexico", "Chiapas": "Mexico", "Colorado Adventure": "Mexico",
    "Winja's Fear": "Wuze Town", "Winja's Force": "Wuze Town", "Crazy Bats": "Wuze Town",
    "Feng Ju Palace": "China", "Geister Rikscha": "China"
}

PHL_WALK_MATRIX = {
    ("Berlin", "Rookburgh"): 2, ("Berlin", "Mexico"): 5,
    ("Berlin", "China"): 8, ("Berlin", "Klugheim"): 6,
    ("Berlin", "Africa"): 8, ("Klugheim", "Mexico"): 3,
    ("Klugheim", "China"): 4, ("Klugheim", "Africa"): 4,
    ("Klugheim", "Rookburgh"): 8, ("Mexico", "Africa"): 3,
    ("Rookburgh", "Wuze Town"): 6
}

# Model laden
try:
    PIPELINE = joblib.load(MODEL_FILE)
    MODEL = PIPELINE["model"]
    ENCODERS = PIPELINE["encoders"]
    FEATURES = PIPELINE["features"]
except:
    MODEL = None

# --- 2. LIVE DATA OPHALEN (MET DE JUISTE HEADERS) ---
def fetch_live_data(park_name):
    park_id = PARK_IDS.get(park_name)
    if not park_id: return {}
    
    print(f"📡 Ophalen data voor {park_name} (ID: {park_id})...") 

    try:
        # DEZE HEADERS ZIJN CRUCIAAL (Dit zijn degene uit je geslaagde test)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        }
        
        # Timeout op 10s zodat hij niet oneindig blijft hangen
        resp = requests.get(f"https://queue-times.com/parks/{park_id}/queue_times.json", headers=headers, timeout=10)
        
        if resp.status_code != 200: 
            print(f"❌ API Fout: Status {resp.status_code}")
            return {}
            
        data = resp.json()
        live = {}
        total, open_cnt = 0, 0
        
        for land in data.get('lands', []):
            for ride in land.get('rides', []):
                raw_name = ride['name'].strip()
                
                # Mapping toepassen
                clean_name = API_NAME_MAPPING.get(raw_name, raw_name)
                
                # Match met Metadata
                if clean_name in ATTRACTION_METADATA:
                    final_name = clean_name
                elif raw_name in ATTRACTION_METADATA:
                    final_name = raw_name
                else:
                    final_name = clean_name

                total += 1
                if ride['is_open']: open_cnt += 1
                
                # Veilig opslaan
                wait = ride.get('wait_time')
                if wait is None: wait = 0
                
                live[final_name] = {
                    "is_open": ride['is_open'], 
                    "wait_time": wait
                }

                # DEBUG: Zie je Symbolica nu wel?
                if "Symbolica" in final_name:
                    print(f"✅ Gevonden in App: {final_name} = {wait} min")

        # Check park sluiting
        if total > 0 and (open_cnt / total) < 0.2: 
            return {}
            
        return live
        
    except Exception as e:
        print(f"❌ Fout bij ophalen data: {e}")
        return {}

# --- 3. HELPER: LOOPTIJDEN ---
def calculate_transit_time(park, start, end):
    if start == end: return 0
    if start == "Unknown" or end == "Unknown": return 5

    if park == "PHANTASIALAND":
        zone_a = PHL_LOCATIONS.get(start, "Berlin")
        zone_b = PHL_LOCATIONS.get(end, "Berlin")
        if zone_a == zone_b: return 3
        
        pair = (zone_a, zone_b)
        rev_pair = (zone_b, zone_a)
        
        if pair in PHL_WALK_MATRIX: return PHL_WALK_MATRIX[pair]
        if rev_pair in PHL_WALK_MATRIX: return PHL_WALK_MATRIX[rev_pair]
        return 10 

    return get_travel_time(start, end)

# --- 4. VOORSPELLING & LOGICA ---
def get_wait_time_prediction(park_name, ride_name, query_time, live_data_snapshot=None, weather_override=None):
    # Timezone fix
    if query_time.tzinfo is not None and query_time.tzinfo.utcoffset(query_time) is not None:
        now = datetime.datetime.now(query_time.tzinfo)
    else:
        now = datetime.datetime.now()

    # Live Data Check (binnen 30 min)
    time_diff_minutes = (query_time - now).total_seconds() / 60
    
    if not weather_override and live_data_snapshot and 0 <= time_diff_minutes < 30:
        if ride_name in live_data_snapshot:
            val = live_data_snapshot[ride_name].get('wait_time')
            if val is None: val = live_data_snapshot[ride_name].get('wait_min')
            
            if val is None: return 0
            if not live_data_snapshot[ride_name]['is_open']: return 999 
            return val

    # Model / Heuristiek fallback
    meta = ATTRACTION_METADATA.get(ride_name, {})
    
    # Weer defaults
    if weather_override:
        w_temp = weather_override.get('temp_c', 15.0)
        w_precip = weather_override.get('precip_mm', 0.0)
        w_cond = weather_override.get('condition', 'Cloudy')
    else:
        w_temp, w_precip, w_cond = 15.0, 0.0, 'Cloudy'

    if MODEL:
        try:
            row = pd.DataFrame([{
                'attraction_name': ride_name, 'park_name': park_name,
                'temp_c': w_temp, 'precip_mm': w_precip, 'weather_condition': w_cond,
                'day_of_week': query_time.isoweekday(), 'hour_of_day': query_time.hour,
                'is_holiday': is_crowd_risk_day(query_time),
                'type': meta.get('type', 'Unknown'), 'zone': meta.get('zone', 'Unknown'),
                'capacity': meta.get('capacity', 0), 'is_indoor': meta.get('is_indoor', 0),
                'hour_sin': np.sin(2 * np.pi * query_time.hour / 24),
                'hour_cos': np.cos(2 * np.pi * query_time.hour / 24),
                'day_sin': np.sin(2 * np.pi * query_time.isoweekday() / 7),
                'day_cos': np.cos(2 * np.pi * query_time.isoweekday() / 7)
            }])
            
            def safe_enc(enc, col): return row[col].map(lambda x: enc.transform([x])[0] if x in enc.classes_ else 0)
            
            row['park_encoded'] = safe_enc(ENCODERS['park'], 'park_name')
            row['ride_encoded'] = safe_enc(ENCODERS['ride'], 'attraction_name')
            row['type_encoded'] = safe_enc(ENCODERS['type'], 'type')
            row['weather_encoded'] = safe_enc(ENCODERS['weather'], 'weather_condition')
            
            pred = MODEL.predict(row[FEATURES])[0]
            return int(5 * round(max(0, pred) / 5))
        except Exception:
            pass 
    
    # Heuristiek fallback
    hour = query_time.hour
    base_wait = 15
    if 12 <= hour <= 15: base_wait += 20
    elif 10 <= hour < 12: base_wait += 10
    
    if weather_override:
        if weather_override.get('precip_mm', 0) > 2.0: base_wait -= 10
        if weather_override.get('temp_c', 20) > 28: base_wait -= 5

    return max(5, base_wait)

def format_time(dt): return dt.strftime('%H:%M')

# --- 5. MAIN SOLVER ---
def solve_route_with_priorities(park_name, must_haves, should_haves, start_str, end_str, start_location="Unknown", lunch_config=None):
    tz = pytz.timezone('Europe/Brussels')
    now_aware = datetime.datetime.now(tz)
    today = now_aware.date()
    
    sh, sm = map(int, start_str.split(':'))
    eh, em = map(int, end_str.split(':'))
    
    current_time = tz.localize(datetime.datetime.combine(today, datetime.time(sh, sm)))
    park_close = tz.localize(datetime.datetime.combine(today, datetime.time(eh, em)))
    
    if park_close < current_time:
         park_close += datetime.timedelta(days=1)

    live_data = fetch_live_data(park_name)
    
    lunch_done = False
    lunch_dt = None
    if lunch_config:
        l_time = lunch_config['time']
        lunch_dt = tz.localize(datetime.datetime.combine(today, l_time))
        if current_time >= lunch_dt: lunch_done = True

    active_must = []
    active_should = []
    closed_rides = []

    all_targets = must_haves + should_haves
    for ride in all_targets:
        if live_data and ride in live_data:
            if not live_data[ride]['is_open']:
                closed_rides.append(ride)
                continue
        
        if ride in must_haves: active_must.append(ride)
        else: active_should.append(ride)

    unvisited = active_must + active_should
    
    current_location = start_location
    if current_location in ["Unknown", "Ingang"]:
        if park_name == "EFTELING": current_location = "Piraña" 
        elif park_name == "PHANTASIALAND": current_location = "Maus au Chocolat"
        elif park_name == "WALIBI_BELGIUM": current_location = "Loup-Garou"

    itinerary = []
    skipped_rides = []
    
    while unvisited or (lunch_config and not lunch_done):
        if current_time >= park_close: 
            skipped_rides.extend(unvisited)
            break

        if lunch_config and not lunch_done and current_time >= lunch_dt:
            rest = lunch_config['restaurant']
            walk = calculate_transit_time(park_name, current_location, rest)
            arr = current_time + datetime.timedelta(minutes=walk)
            fin = arr + datetime.timedelta(minutes=lunch_config['duration'])
            
            itinerary.append({
                "ride": f"🍽️ Lunch: {rest}", "type": "LUNCH",
                "start_walk": format_time(current_time), "walk_min": int(walk),
                "arrival_time": format_time(arr), "wait_min": 0,
                "ride_start": format_time(arr), "ride_end": format_time(fin),
                "note": f"{lunch_config['duration']} min pauze"
            })
            current_time = fin
            current_location = rest
            lunch_done = True
            continue

        if not unvisited: break

        best_cand, best_score, best_det = None, float('inf'), {}

        for ride in unvisited:
            walk_time = calculate_transit_time(park_name, current_location, ride)
            arrival_time = current_time + datetime.timedelta(minutes=walk_time)
            
            if arrival_time >= park_close: continue 

            wait_now = get_wait_time_prediction(park_name, ride, arrival_time, live_data)
            
            if isinstance(wait_now, dict): wait_now = 15
            if wait_now >= 999: continue 

            cost = walk_time + wait_now
            
            if ride in active_should: cost *= 1.5 
            if ride in active_must and wait_now < 15: cost *= 0.7 

            if cost < best_score:
                best_score = cost
                best_cand = ride
                best_det = {"walk": walk_time, "wait": wait_now, "arrival": arrival_time}

        if not best_cand: 
            skipped_rides.extend(unvisited)
            break 

        ride = best_cand
        dur = ATTRACTION_METADATA.get(ride, {}).get('duration_min', 5)
        
        ride_start_dt = best_det['arrival'] + datetime.timedelta(minutes=best_det['wait'])
        ride_end_dt = ride_start_dt + datetime.timedelta(minutes=dur)
        
        # --- AANGEPASTE LIVE DATA LOGIC ---
        is_live = False
        if live_data and ride in live_data:
            # Bereken het verschil tussen de GEPLANDE AANKOMST en NU
            diff_seconds = (best_det['arrival'] - now_aware).total_seconds()
            
            # Alleen label 'Live' tonen als aankomst binnen 30 minuten (1800 sec) is
            if 0 <= diff_seconds < 1800:
                is_live = True
        # ----------------------------------

        itinerary.append({
            "ride": ride, 
            "type": "MUST" if ride in active_must else "SHOULD",
            "start_walk": format_time(current_time), 
            "walk_min": int(best_det['walk']),
            "arrival_time": format_time(best_det['arrival']), 
            "wait_min": int(best_det['wait']),
            "ride_start": format_time(ride_start_dt), 
            "ride_end": format_time(ride_end_dt), 
            "note": "⚡ Live Data" if is_live else "🔮 Forecast"
        })
        
        current_time = ride_end_dt
        current_location = ride
        unvisited.remove(ride)

    return itinerary, closed_rides, skipped_rides