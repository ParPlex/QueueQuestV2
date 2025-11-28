import requests
import json

print("1. Start test verbinding...")
try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    }
    # Efteling ID = 160
    url = "https://queue-times.com/parks/160/queue_times.json"
    
    print(f"2. Verzoek sturen naar {url}...")
    resp = requests.get(url, headers=headers, timeout=10)
    
    print(f"3. Status Code: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"4. ✅ SUCCES! {len(str(data))} bytes ontvangen.")
        
        # Check Symbolica
        for land in data['lands']:
            for ride in land['rides']:
                if "Symbolica" in ride['name']:
                    print(f"   🎢 Gevonden: {ride['name']} - Wacht: {ride['wait_time']} min")
    else:
        print("4. ❌ Mislukt: Geen 200 OK.")
        print(resp.text[:200])

except Exception as e:
    print(f"4. 💥 CRASH: {e}")