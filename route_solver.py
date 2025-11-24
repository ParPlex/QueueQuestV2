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

# ==============================================================================
# DEEL 1: VOORSPEL LOGICA (AI)
# ==============================================================================

def get_wait_time_prediction(park_name, ride_name, query_time):
    """
    Voorspelt de wachttijd voor één enkele attractie op één moment.
    """
    is_holiday = is_crowd_risk_day(query_time)
    meta = ATTRACTION_METADATA.get(ride_name, {})
    
    if meta.get('park') != park_name: return 999

    # Input rij maken
    row = pd.DataFrame([{
        'attraction_name': ride_name,
        'park_name': park_name,
        'temp_c': 15.0,        
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
    }])

    # Encoden
    try:
        def safe_transform(encoder, col_name):
            return row[col_name].map(lambda x: encoder.transform([x])[0] if x in encoder.classes_ else 0)

        row['park_encoded'] = safe_transform(ENCODERS['park'], 'park_name')
        row['ride_encoded'] = safe_transform(ENCODERS['ride'], 'attraction_name')
        row['type_encoded'] = safe_transform(ENCODERS['type'], 'type')
        row['weather_encoded'] = safe_transform(ENCODERS['weather'], 'weather_condition')
        
        # Voorspellen
        X = row[FEATURES]
        pred = MODEL.predict(X)[0]
        return int(5 * round(max(0, pred) / 5))
    except Exception:
        return 0

# ==============================================================================
# DEEL 2: SLIMME DAGPLANNER LOGICA
# ==============================================================================

def get_best_future_wait(park_name, ride, current_time, end_time):
    """
    Scant de toekomst (tot sluitingstijd) om te zien wat de LAAGST mogelijke wachttijd is.
    """
    min_wait = 999
    check_time = current_time
    
    # Check elk half uur tot sluitingstijd
    while check_time < end_time:
        wait = get_wait_time_prediction(park_name, ride, check_time)
        if wait < min_wait:
            min_wait = wait
        check_time += datetime.timedelta(minutes=30)
        
    return min_wait

def format_time(dt):
    return dt.strftime('%H:%M')

def solve_route(park_name, wishlist, start_time_str="10:00", park_close_str="18:00"):
    # Tijd setup
    now = datetime.datetime.now()
    sh, sm = map(int, start_time_str.split(':'))
    eh, em = map(int, park_close_str.split(':'))
    
    current_time = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    park_close_time = now.replace(hour=eh, minute=em, second=0, microsecond=0)
    
    if current_time < now: 
        current_time += datetime.timedelta(days=1)
        park_close_time += datetime.timedelta(days=1)
        
    unvisited = wishlist.copy()
    
    # Startlocatie
    current_location = "Unknown"
    if park_name == "EFTELING": current_location = "Piraña"
    elif park_name == "PHANTASIALAND": current_location = "Maus au Chocolat"
    elif park_name == "WALIBI_BELGIUM": current_location = "Loup-Garou"

    itinerary = []
    total_wait = 0
    total_walk = 0

    print(f"\n🚀 Start Dagplanning voor {park_name}")
    print(f"🕒 Tijdvak: {format_time(current_time)} - {format_time(park_close_time)}")
    print(f"🎯 Doelen: {', '.join(unvisited)}\n")

    while unvisited:
        # Check of we nog tijd hebben
        if current_time >= park_close_time:
            print("⚠️ WAARSCHUWING: Park gaat dicht, niet alles gelukt!")
            break

        best_candidate = None
        best_score = float('inf') # Lagere score is beter
        best_details = {}

        # We evalueren elke kandidaat op basis van een Slimme Score
        for ride in unvisited:
            # 1. Reistijd & Aankomst
            walk_time = get_travel_time(current_location, ride)
            arrival_time = current_time + datetime.timedelta(minutes=walk_time)
            
            # 2. Wachttijd NU (bij aankomst)
            wait_now = get_wait_time_prediction(park_name, ride, arrival_time)
            
            # 3. Wachttijd LATER (beste moment in de rest van de dag)
            # We kijken alleen in de toekomst als er nog meer dan 2 uur over is
            time_left = (park_close_time - arrival_time).total_seconds() / 3600
            
            regret_penalty = 0
            if time_left > 1.5: 
                best_future_wait = get_best_future_wait(park_name, ride, arrival_time, park_close_time)
                
                # Als het nu veel drukker is dan het beste moment, krijg je strafpunten
                diff = wait_now - best_future_wait
                if diff > 5: # Alleen boeien als het verschil > 5 min is
                    regret_penalty = diff * 2.5 # Factor 2.5: Wachten 'voelt' zwaarder dan lopen
            
            # 4. Score Berekening
            # Score = (Lopen) + (Wachten Nu) + (Spijt dat je niet wacht)
            score = walk_time + wait_now + regret_penalty
            
            # Debug printje (kun je aanzetten om te zien hoe hij denkt)
            # print(f"   Optie {ride}: Walk {walk_time} + Wait {wait_now} + Regret {regret_penalty} = Score {score}")

            if score < best_score:
                best_score = score
                best_candidate = ride
                best_details = {"walk": walk_time, "wait": wait_now, "arrival": arrival_time}

        # --- De Beste Keuze is Gemaakt ---
        ride = best_candidate
        
        # Uitvoeren
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
            "ride_end": format_time(finish_time),
            "note": "✅ Optimale tijd!" if best_details['wait'] <= 15 else "⚠️ Druk, maar beste optie"
        })
        
        current_time = finish_time
        current_location = ride
        unvisited.remove(ride)

    return itinerary, total_wait, total_walk

# --- TESTEN ---
if __name__ == "__main__":
    wishlist = ["Baron 1898", "Symbolica", "Python", "Droomvlucht", "Vogel Rok", "Joris en de Draak", "Carnaval Festival"]
    park = "EFTELING"
    
    route, tot_wait, tot_walk = solve_route(park, wishlist, "10:00", "19:00")
    
    print("-" * 95)
    print(f"{'TIJD':<8} | {'ACTIVITEIT':<30} | {'DETAILS':<25} | {'OPMERKING'}")
    print("-" * 95)
    
    for step in route:
        print(f"{step['start_walk']:<8} | 🚶 Loop naar {step['ride']:<20} | {step['walk_min']} min lopen           |")
        print(f"{step['arrival_time']:<8} | ⏳ Wachtrij {step['ride']:<20} | {step['wait_min']} min wachten         | {step['note']}")
        print(f"{step['ride_start']:<8} | 🎢 Ritje in {step['ride']:<20} | Tot {step['ride_end']}             |")
        print("-" * 95)
        
    print(f"\n✅ Dagplanning compleet! Totaal {tot_wait} min gewacht, {tot_walk} min gelopen.")