import datetime
import random
from route_solver import solve_route
from distance_utils import get_travel_time
from predict_logic import get_future_wait_times
from queuequest_meta import ATTRACTION_METADATA

def simulate_naive_route(park_name, wishlist, start_time_str="10:00"):
    """
    Simuleert een toerist die steeds naar de dichtstbijzijnde attractie loopt,
    zonder rekening te houden met wachttijden.
    """
    now = datetime.datetime.now()
    sh, sm = map(int, start_time_str.split(':'))
    current_time = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    if current_time < now: current_time += datetime.timedelta(days=1)
    
    # Startlocatie
    current_location = "Unknown"
    if park_name == "EFTELING": current_location = "Piraña"
    elif park_name == "PHANTASIALAND": current_location = "Maus au Chocolat"
    elif park_name == "WALIBI_BELGIUM": current_location = "Loup-Garou"

    unvisited = wishlist.copy()
    total_wait = 0
    total_walk = 0
    route_log = []

    while unvisited:
        # STRATEGIE: Zoek fysiek dichtstbijzijnde
        nearest_ride = min(unvisited, key=lambda r: get_travel_time(current_location, r))
        
        # 1. Reizen
        walk_time = get_travel_time(current_location, nearest_ride)
        arrival_time = current_time + datetime.timedelta(minutes=walk_time)
        
        # 2. Wachten (We vragen de AI: hoe druk is het DAN?)
        preds = get_future_wait_times(park_name, [nearest_ride], arrival_time)
        wait_time = preds.get(nearest_ride, 0)
        
        # 3. Rit
        meta = ATTRACTION_METADATA.get(nearest_ride, {})
        duration = meta.get('duration_min', 5)
        
        # Update
        total_walk += walk_time
        total_wait += wait_time
        
        route_log.append(nearest_ride)
        
        # Tijd vooruit
        current_time = arrival_time + datetime.timedelta(minutes=wait_time + duration)
        current_location = nearest_ride
        unvisited.remove(nearest_ride)
        
    return total_wait, total_walk, route_log

def run_benchmark():
    park = "EFTELING"
    start_time = "10:00"
    end_time = "19:00"
    wishlist = ["Baron 1898", "Symbolica", "Python", "Droomvlucht", "Vogel Rok", "Joris en de Draak", "Carnaval Festival"]
    
    print(f"🏁 START BENCHMARK: {park}")
    print(f"🎯 Doelen: {', '.join(wishlist)}")
    print("-" * 60)

    # 1. SLIMME ROUTE (Met Spijt-Factor)
    smart_route, s_wait, s_walk = solve_route(park, wishlist, start_time, end_time)
    s_total_lost = s_wait + s_walk
    
    print(f"\n🧠 SLIMME ROUTE (QueueQuest)")
    print(f"   Totaal 'verloren': {s_total_lost} min (Wacht: {s_wait}, Loop: {s_walk})")
    # Print volgorde
    order = [step['ride'] for step in smart_route]
    print(f"   Volgorde: {' -> '.join(order)}")

    # 2. NAÏEVE ROUTE (Nearest Neighbor)
    n_wait, n_walk, n_order = simulate_naive_route(park, wishlist, start_time)
    n_total_lost = n_wait + n_walk
    
    print(f"\n🚶 NAÏEVE ROUTE (Dichtstbijzijnde eerst)")
    print(f"   Totaal 'verloren': {n_total_lost} min (Wacht: {n_wait}, Loop: {n_walk})")
    print(f"   Volgorde: {' -> '.join(n_order)}")

    # 3. RESULTAAT
    print("\n" + "="*40)
    diff = n_total_lost - s_total_lost
    if diff > 0:
        print(f"✅ JE AI IS SNELLER!")
        print(f"🚀 Je bespaart {diff} minuten t.o.v. zelf rondlopen.")
    else:
        print(f"🤔 Hmmm, de naïeve route was sneller. (Kan gebeuren op rustige dagen)")

if __name__ == "__main__":
    run_benchmark()