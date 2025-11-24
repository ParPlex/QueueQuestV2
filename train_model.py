import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import LabelEncoder
import joblib
from queuequest_meta import ATTRACTION_METADATA

# --- CONFIGURATIE ---
INPUT_FILE = "mock_data.csv"
MODEL_FILE = "queuequest_model.pkl"

def prepare_data(df):
    print("Feature Engineering gestart...")
    
    # 1. Metadata toevoegen (Type, Zone, Capaciteit)
    # We maken een dictionary om snel op te zoeken
    meta_df = pd.DataFrame.from_dict(ATTRACTION_METADATA, orient='index')
    
    # Voeg metadata toe aan de hoofd data
    # We mappen op 'attraction_name'
    df['type'] = df['attraction_name'].map(lambda x: ATTRACTION_METADATA.get(x, {}).get('type', 'Unknown'))
    df['zone'] = df['attraction_name'].map(lambda x: ATTRACTION_METADATA.get(x, {}).get('zone', 'Unknown'))
    df['capacity'] = df['attraction_name'].map(lambda x: ATTRACTION_METADATA.get(x, {}).get('capacity', 0))
    df['is_indoor'] = df['attraction_name'].map(lambda x: ATTRACTION_METADATA.get(x, {}).get('is_indoor', 0))

    # 2. Tijd Features (Cyclisch maken)
    # 23:00 uur moet dicht bij 00:00 uur liggen voor een AI. Sinus/Cosinus helpt daarbij.
    df['hour_sin'] = np.sin(2 * np.pi * df['hour_of_day'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour_of_day'] / 24)
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

    # 3. Categorische Data omzetten naar nummers (Label Encoding)
    # XGBoost houdt van nummers, geen tekst.
    le_park = LabelEncoder()
    df['park_encoded'] = le_park.fit_transform(df['park_name'])
    
    le_ride = LabelEncoder()
    df['ride_encoded'] = le_ride.fit_transform(df['attraction_name'])
    
    le_type = LabelEncoder()
    df['type_encoded'] = le_type.fit_transform(df['type'])
    
    le_weather = LabelEncoder()
    df['weather_encoded'] = le_weather.fit_transform(df['weather_condition'])

    # Sla de encoders op zodat we ze later kunnen gebruiken bij voorspellingen
    encoders = {
        'park': le_park,
        'ride': le_ride,
        'type': le_type,
        'weather': le_weather
    }

    # 4. Opschonen (Verwijder tekstkolommen die we nu gecodeerd hebben)
    features_to_drop = ['timestamp', 'attraction_name', 'park_name', 'type', 'zone', 'weather_condition']
    df_train = df.drop(columns=features_to_drop)
    
    return df_train, encoders

def train_model():
    # 1. Data Laden
    print(f"Data laden uit {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    
    # 2. Voorbereiden
    df_train, encoders = prepare_data(df)
    
    # Doelvariabele (Wat willen we voorspellen?)
    target = 'posted_wait_time_min'
    features = [col for col in df_train.columns if col != target]
    
    X = df_train[features]
    y = df_train[target]
    
    # 3. Split in Train (80%) en Test (20%) set
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 4. Het Model Initialiseren (XGBoost Regressor)
    print("Start training XGBoost model... (Dit kan even duren)")
    model = xgb.XGBRegressor(
        n_estimators=500,    # Aantal 'beslisbomen'
        learning_rate=0.05,  # Hoe snel hij leert
        max_depth=6,         # Hoe complex de bomen mogen zijn
        n_jobs=-1            # Gebruik alle processor cores
    )
    
    # 5. Trainen!
    model.fit(X_train, y_train)
    
    # 6. Evalueren
    predictions = model.predict(X_test)
    mae = mean_absolute_error(y_test, predictions)
    print(f"\n--- Resultaten ---")
    print(f"Gemiddelde afwijking (MAE): {mae:.2f} minuten")
    print("Dat betekent: gemiddeld zit het model er zoveel minuten naast.")
    
    # 7. Opslaan
    full_pipeline = {
        "model": model,
        "encoders": encoders,
        "features": features
    }
    joblib.dump(full_pipeline, MODEL_FILE)
    print(f"\nModel succesvol opgeslagen als '{MODEL_FILE}'")

if __name__ == "__main__":
    train_model()