import joblib
import pandas as pd
import numpy as np
import datetime
from queuequest_meta import ATTRACTION_METADATA
from holiday_utils import is_crowd_risk_day
from distance_utils import get_travel_time

# --- CONFIGURATIE & MODEL LADEN ---
MODEL_FILE = "queuequest_model.pkl"

print(f"⚙️ Model laden uit '{MODEL_FILE}'...")
try:
    PIPELINE = joblib.load(MODEL_FILE)
    MODEL = PIPELINE["model"]
    ENCODERS = PIPELINE["encoders"]
    FEATURES = PIPELINE["features"]
    print("✅ Model succesvol geladen!")
except FileNotFoundError:
    print(f"❌ FOUT: Kan '{MODEL_FILE}' niet vinden.")
    exit()

# --- DEEL 1: VOORSPEL LOGICA (AI) ---

def get_future_wait_times(park_name, ride_list, query_time):
    """
    Voorspelt wachttijden met behulp van het XGBoost model.
    """
    is_holiday = is_crowd_risk_day(query_time)
    input_rows = []
    
    for ride_name in ride_list:
        meta = ATTRACTION_METADATA.get(ride_name, {})
        if meta.get('park') != park_name: continue

        input_rows.append({
            'attraction_name': ride_name,
            'park_name': park_name,
            'temp_c': 15.0,        # Fictief weer
            'precip_mm': 0.0,      
            'weather_condition': 'Cloudy', 
            'day_of_week': query_time.isoweekday(),
            'hour_of_day': query_time.hour,
            'is_holiday': is_holiday,
            'type': meta.get('type', 'Unknown'),
            'zone': meta.get('zone', 'Unknown'),
            'capacity': meta.get('capacity', 0),
            'is_indoor': meta.get('is_indoor', 0),
            'hour_sin': np.sin(2 * np.pi * query_time.hour / 24),
            'hour_cos': np.cos(2 * np.pi * query_time.hour / 24),
            'day_sin': np.sin(2 * np.pi * query_time.isoweekday() / 7),
            'day_cos': np.cos(2 * np.pi * query_time.isoweekday() / 7)
        })

    if not input_rows: return {}

    # DataFrame maken en encoden
    df = pd.DataFrame(input_rows)
    try:
        def safe_transform(encoder, col_name):
            return df[col_name].map(lambda x: encoder.transform([x])[0] if x in encoder.classes_ else 0)

        df['park_encoded'] = safe_transform(ENCODERS['park'], 'park_name')
        df['ride_encoded'] = safe_transform(ENCODERS['ride'], 'attraction_name')
        df['type_encoded'] = safe_transform(ENCODERS['type'], 'type')
        df['weather_encoded'] = safe_transform(ENCODERS['weather'], 'weather_condition')
        
        # Voorspellen
        X = df[FEATURES]
        predictions = MODEL.predict(X)
    except Exception as e:
        print(f"Fout in voorspelling: {e}")
        return {}
    
    result = {}
    for i, ride_name in enumerate(df['attraction_name']):
        raw = max(0, predictions[i])
        result[ride_name] = int(5 * round(raw / 5)) # Afronden op 5 min
        
    return result

# --- DEEL 2: ROUTE PLANNER (SOLVER) ---

def format_time(dt):
    return dt.strftime('%H:%M')

def solve_route(park_name, start_rides, start_time_str="10:00"):
    """
    Berekent de optimale route.
    """
    now = datetime.datetime.now()
    start_hour, start_min = map(int, start_time_str.split(':'))
    current_time = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
    
    if current_time < now: current_time += datetime.timedelta(days=1)
        
    unvisited = start_rides.copy()
    
    # Bepaal startlocatie
    current_location = "Unknown"
    if park_name == "EFTELING": current_location = "Piraña" # Vlakbij ingang
    elif park_name == "PHANTASIALAND": current_location = "Maus au Chocolat"
    elif park_name == "WALIBI_BELGIUM": current_location = "Loup-Garou"

    itinerary = []
    total_wait = 0
    total_walk = 0

    print(f"\n🚀 Start Routeberekening voor {park_name} om {format_time(current_time)}")
    print(f"🎯 Doelen: {', '.join(unvisited)}\n")

    while unvisited:
        best_next_step = None
        best_cost = float('inf')
        best_details = {}

        # Zoek de beste volgende stap (Greedy Lookahead)
        for candidate in unvisited:
            # 1. Hoe lang lopen?
            walk_time = get_travel_time(current_location, candidate)
            arrival_time = current_time + datetime.timedelta(minutes=walk_time)
            
            # 2. Hoe lang wachten BIJ AANKOMST?
            preds = get_future_wait_times(park_name, [candidate], arrival_time)
            predicted_wait = preds.get(candidate, 0)
            
            # 3. Kosten = Lopen + Wachten
            cost = walk_time + predicted_wait
            
            if cost < best_cost:
                best_cost = cost
                best_next_step = candidate
                best_details = {"walk": walk_time, "wait": predicted_wait, "arrival": arrival_time}

        # Voer de stap uit
        ride = best_next_step
        meta = ATTRACTION_METADATA.get(ride, {})
        duration = meta.get('duration_min', 5)
        
        total_walk += best_details['walk']
        total_wait += best_details['wait']
        
        finish_time = best_details['arrival'] + datetime.timedelta(minutes=best_details['wait'] + duration)
        
        itinerary.append({
            "ride": ride,
            "start_walk": format_time(current_time),
            "walk_min": best_details['walk'],
            "arrival_time": format_time(best_details['arrival']),
            "wait_min": best_details['wait'],
            "ride_start": format_time(best_details['arrival'] + datetime.timedelta(minutes=best_details['wait'])),
            "ride_end": format_time(finish_time)
        })
        
        current_time = finish_time
        current_location = ride
        unvisited.remove(ride)

    return itinerary, total_wait, total_walk

# --- TEST SCENARIO ---
if __name__ == "__main__":
    print("--- QueueQuest Route Solver (Gecombineerd) ---")
    
    # Kies hier je test scenario:
    my_wishlist = ["Baron 1898", "Symbolica", "Python", "Droomvlucht", "Vogel Rok"]
    park = "EFTELING"
    
    # my_wishlist = ["Taron", "Black Mamba", "F.L.Y.", "Maus au Chocolat"]
    # park = "PHANTASIALAND"
    
    route, tot_wait, tot_walk = solve_route(park, my_wishlist, "10:00")
    
    print("-" * 75)
    print(f"{'TIJD':<8} | {'ACTIVITEIT':<35} | {'DETAILS'}")
    print("-" * 75)
    
    for step in route:
        print(f"{step['start_walk']:<8} | 🚶 Loop naar {step['ride']:<25} | {step['walk_min']} min")
        print(f"{step['arrival_time']:<8} | ⏳ Wachtrij {step['ride']:<25} | {step['wait_min']} min")
        print(f"{step['ride_start']:<8} | 🎢 Ritje in {step['ride']:<25} | Tot {step['ride_end']}")
        print("-" * 75)
        
    print(f"\n✅ Klaar! Totaal wachten: {tot_wait} min. Totaal wandelen: {tot_walk} min.")