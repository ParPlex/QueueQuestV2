import pandas as pd
import datetime
import random
from queuequest_meta import ATTRACTION_METADATA
from holiday_utils import is_crowd_risk_day

# Instellingen
DAYS_OF_DATA = 45
START_DATE = datetime.datetime.now() - datetime.timedelta(days=DAYS_OF_DATA)
PARK_HOURS = (10, 19) # Iets langer open voor de simulatie

def get_time_factor(hour):
    """
    Simuleert de drukte-curve van een dag.
    """
    if hour < 11:
        return 0.6  # Ochtend is rustig (60% van normaal)
    elif 11 <= hour < 13:
        return 1.1  # Opbouw naar piek
    elif 13 <= hour < 16:
        return 1.3  # Piekdrukte (130%)
    elif 16 <= hour < 17:
        return 0.9  # Begint af te nemen
    else:
        return 0.5  # Avond is heerlijk rustig (50%)

def generate_mock_data():
    data = []
    current_time = START_DATE
    end_time = datetime.datetime.now()
    
    print(f"Start genereren van {DAYS_OF_DATA} dagen 'Slimme' data...")

    while current_time < end_time:
        if PARK_HOURS[0] <= current_time.hour < PARK_HOURS[1]:
            
            # Context
            is_raining = random.random() < 0.25 
            temp_base = 15 - (0.5 * abs(current_time.month - 7))
            temp = temp_base + random.uniform(-3, 3)
            precip = random.uniform(0.5, 8.0) if is_raining else 0.0
            
            crowd_risk = is_crowd_risk_day(current_time)
            crowd_factor = 1.5 if crowd_risk == 1 else 1.0 
            
            # HAAL DE TIJD FACTOR OP
            time_factor = get_time_factor(current_time.hour)

            for ride_name, meta in ATTRACTION_METADATA.items():
                
                # Basis wachttijd
                base_wait = random.randint(10, 40)
                
                # Weersinvloeden
                if meta['is_indoor'] == 0 and is_raining:
                    base_wait *= 0.3 
                elif meta['is_indoor'] == 1 and is_raining:
                    base_wait *= 1.4 
                
                # Capaciteit & Populariteit
                if meta['capacity'] > 1500: base_wait *= 0.8
                if meta['capacity'] < 1300 and meta['type'] == 'Coaster': base_wait += 15 

                # TOTALE WACHTTIJD FORMULE
                # Basis * Drukte(Weekend) * Tijd(Ochtend/Avond)
                final_wait = int(base_wait * crowd_factor * time_factor)
                
                data.append({
                    "timestamp": current_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "park_name": meta['park'],
                    "attraction_name": ride_name,
                    "posted_wait_time_min": max(0, final_wait),
                    "temp_c": round(temp, 1),
                    "precip_mm": round(precip, 1),
                    "weather_condition": "Rain" if is_raining else "Cloudy",
                    "day_of_week": current_time.isoweekday(),
                    "hour_of_day": current_time.hour,
                    "is_holiday": crowd_risk
                })
        
        current_time += datetime.timedelta(minutes=15)

    df = pd.DataFrame(data)
    df.to_csv("mock_data.csv", index=False)
    print("Klaar! Nieuwe data met dag-curves gegenereerd.")

if __name__ == "__main__":
    generate_mock_data()