import boto3
import pandas as pd
from decimal import Decimal
import os
import sys
import datetime

# --- CONFIGURATIE ---
TABLE_NAME = 'QueueQuestLogs'
OUTPUT_FILE = 'real_data.csv'
# Zorg dat dit de regio is waar je tabel staat (Stockholm = eu-north-1)
REGION = os.environ.get('AWS_REGION', 'eu-north-1') 

def fetch_and_process_real_data():
    """Haalt alle data op uit DynamoDB, converteert Decimals en slaat op als CSV."""
    
    try:
        # Boto3 zoekt hier naar de credentials die je met 'aws configure' hebt ingesteld
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        table = dynamodb.Table(TABLE_NAME)
    except Exception as e:
        print(f"❌ FOUT: Kan niet verbinden met AWS. Is de REGION '{REGION}' juist?")
        print(f"Details: {e}")
        sys.exit(1)

    print(f"⏳ Verbinding met tabel '{TABLE_NAME}' in '{REGION}'...")
    print("   Data aan het downloaden (Scan met paginatie)...")
    
    # Gebruik Scan om alle items op te halen
    try:
        response = table.scan()
        data = response['Items']
        
        # Paginatie: haal alle vervolgpagina's op
        while 'LastEvaluatedKey' in response:
            print(f"... Meer data ophalen ({len(data)} records tot nu toe)")
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            data.extend(response['Items'])
            
    except Exception as e:
        print(f"❌ FOUT: Fout bij het scannen van de tabel. Check IAM rechten.")
        print(f"Details: {e}")
        sys.exit(1)
        
    print(f"✅ Download compleet! {len(data)} records gevonden.")

    if len(data) == 0:
        print("⚠️ De tabel is leeg. Er valt nog niets op te slaan.")
        return

    # 1. Conversie van DynamoDB Decimal naar Python float/int
    clean_data = []
    for item in data:
        clean_item = {}
        for k, v in item.items():
            if isinstance(v, Decimal):
                # Conversie: zonder decimalen wordt int, anders float
                clean_item[k] = int(v) if v % 1 == 0 else float(v)
            else:
                clean_item[k] = v
        
        # De Sort Key (SK) bevat de timestamp in ISO-formaat
        clean_item['timestamp'] = clean_item.get('SK') 
        clean_data.append(clean_item)
        
    # 2. Opslaan als Pandas DataFrame (Hier zat de fout)
    df = pd.DataFrame(clean_data)
    
    # Filteren op de kolommen die het AI-model verwacht
    cols_to_keep = [
        'timestamp', 'park_name', 'attraction_name', 'posted_wait_time_min',
        'temp_c', 'precip_mm', 'weather_condition', 'day_of_week', 'hour_of_day', 'is_holiday'
    ]
    
    # Zorg dat we alleen kolommen pakken die ook echt bestaan in de data
    existing_cols = [c for c in cols_to_keep if c in df.columns]
    
    if not existing_cols:
        print("❌ FOUT: De opgehaalde data bevat niet de juiste kolommen.")
        print(f"Gevonden kolommen: {df.columns}")
        return

    df = df[existing_cols]

    # Sorteren op tijd
    if 'timestamp' in df.columns:
        df = df.sort_values(by='timestamp').reset_index(drop=True)
    
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"🎉 Succes! Data opgeslagen in '{OUTPUT_FILE}' ({len(df)} rijen).")
    print("Je kunt nu 'train_model.py' draaien met INPUT_FILE = 'real_data.csv'")


if __name__ == "__main__":
    fetch_and_process_real_data()