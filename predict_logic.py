import joblib
import pandas as pd
import numpy as np
import datetime
from queuequest_meta import ATTRACTION_METADATA
from holiday_utils import is_crowd_risk_day

# --- CONFIGURATIE ---
MODEL_FILE = "queuequest_model.pkl"

# Model laden
print(f"Model laden uit '{MODEL_FILE}'...")
try:
    PIPELINE = joblib.load(MODEL_FILE)
    MODEL = PIPELINE["model"]
    ENCODERS = PIPELINE["encoders"]
    FEATURES = PIPELINE["features"]
    print("Model succesvol geladen!")
except FileNotFoundError:
    print(f"FOUT: Kan '{MODEL_FILE}' niet vinden. Draai eerst 'train_model.py'.")
    exit()

def get_future_wait_times(park_name, ride_list, query_time):
    """
    Voorspelt wachttijden voor een lijst attracties op een specifiek tijdstip.
    """
    is_holiday = is_crowd_risk_day(query_time)
    input_rows = []
    
    for ride_name in ride_list:
        meta = ATTRACTION_METADATA.get(ride_name, {})
        
        # Check of attractie in dit park hoort
        if meta.get('park') != park_name:
            continue

        row = {
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
        }
        input_rows.append(row)

    if not input_rows:
        return {}

    # DataFrame maken
    df = pd.DataFrame(input_rows)
    
    # Encoders toepassen (veilig)
    try:
        # Hulpfunctie voor veilig encoden
        def safe_transform(encoder, col_name):
            return df[col_name].map(
                lambda x: encoder.transform([x])[0] if x in encoder.classes_ else 0
            )

        df['park_encoded'] = safe_transform(ENCODERS['park'], 'park_name')
        df['ride_encoded'] = safe_transform(ENCODERS['ride'], 'attraction_name')
        df['type_encoded'] = safe_transform(ENCODERS['type'], 'type')
        df['weather_encoded'] = safe_transform(ENCODERS['weather'], 'weather_condition')

    except Exception as e:
        print(f"Encoding Fout: {e}")
        return {}

    # Voorspellen
    try:
        X = df[FEATURES]
        predictions = MODEL.predict(X)
    except KeyError as e:
        print(f"Missende kolommen: {e}")
        return {}
    
    # Resultaat afronden
    result = {}
    for i, ride_name in enumerate(df['attraction_name']):
        raw_pred = max(0, predictions[i])
        result[ride_name] = int(5 * round(raw_pred / 5))
        
    return result

if __name__ == "__main__":
    # Korte test
    future_time = datetime.datetime.now() + datetime.timedelta(days=1)
    future_time = future_time.replace(hour=14, minute=0)
    print(f"Test voor {future_time}:")
    print(get_future_wait_times("EFTELING", ["Baron 1898", "Symbolica"], future_time))