import math
from queuequest_meta import ATTRACTION_METADATA

# --- CONFIGURATIE ---
WALKING_SPEED_KMH = 4.5  # Gemiddelde wandelsnelheid
DETOUR_FACTOR = 1.4      # Paden kronkelen, je loopt nooit in een rechte lijn

# GPS Coördinaten van de zone-centra
ZONE_LOCATIONS = {
    # 🇳🇱 DE EFTELING
    "EFTELING": {
        "Marerijk":     (51.6505, 5.0425),
        "Ruigrijk":     (51.6485, 5.0505),
        "Anderrijk":    (51.6475, 5.0460),
        "Reizenrijk":   (51.6525, 5.0475),
        "Fantasierijk": (51.6510, 5.0455),
        "Unknown":      (51.6500, 5.0450)
    },
    
    # 🇩🇪 PHANTASIALAND (Brühl is compact maar vol bochten)
    "PHANTASIALAND": {
        "Berlin":         (50.8001, 6.8790), # Entree & Maus au Chocolat
        "Klugheim":       (50.7996, 6.8828), # Taron
        "Deep in Africa": (50.7990, 6.8805), # Black Mamba
        "Mexico":         (50.7993, 6.8823), # Chiapas / Talocan
        "Mystery":        (50.8000, 6.8841), # Mystery Castle / River Quest
        "China Town":     (50.7992, 6.8835), # Feng Ju Palace
        "Fantasy":        (50.8005, 6.8780), # Wuze Town / Winja's
        "Rookburgh":      (50.8000, 6.8795), # F.L.Y. (Ligt centraal/achter Berlin)
        "Unknown":        (50.7998, 6.8810)
    },

    # 🇧🇪 WALIBI BELGIUM (Langgerekt park rondom het meer)
    "WALIBI_BELGIUM": {
        "Exotic World": (50.6977, 4.5850), # Kondaa / Tiki-Waka (Achterin)
        "Karma World":  (50.7005, 4.5941), # Cobra / Popcorn Revenge
        "Dock World":   (50.6988, 4.5903), # Pulsar / Psyké
        "Fun World":    (50.7008, 4.5902), # Weerwolf / Kinderland (Centraal)
        "Wild West":    (50.6990, 4.5874), # Calamity Mine / Dalton Terror
        "Unknown":      (50.6995, 4.5890)
    }
}

def haversine_distance(coord1, coord2):
    """Berekent afstand in meters (vogelvlucht)."""
    R = 6371000 
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def get_travel_time(ride_name_a, ride_name_b):
    """Geeft wandeltijd in minuten tussen twee attracties."""
    meta_a = ATTRACTION_METADATA.get(ride_name_a)
    meta_b = ATTRACTION_METADATA.get(ride_name_b)

    # Validatie
    if not meta_a or not meta_b: return 5
    if meta_a['park'] != meta_b['park']: return 9999 # Ander park
    if ride_name_a == ride_name_b: return 0
    
    # Zelfde zone = korte wandeling
    zone_a = meta_a.get('zone', 'Unknown')
    zone_b = meta_b.get('zone', 'Unknown')
    if zone_a == zone_b: return 3 

    # Verschillende zones = Bereken GPS afstand
    park_zones = ZONE_LOCATIONS.get(meta_a['park'])
    coord_a = park_zones.get(zone_a, park_zones.get("Unknown"))
    coord_b = park_zones.get(zone_b, park_zones.get("Unknown"))

    dist_meters = haversine_distance(coord_a, coord_b)
    real_dist = dist_meters * DETOUR_FACTOR # Correctie voor paden
    
    # Snelheid (m/min) en tijd
    speed_m_min = (WALKING_SPEED_KMH * 1000) / 60
    return int(math.ceil(real_dist / speed_m_min))

if __name__ == "__main__":
    print(f"Looptest Walibi: Kondaa -> Cobra: {get_travel_time('Kondaa', 'Cobra')} min")
    print(f"Looptest Phantasialand: Taron -> Black Mamba: {get_travel_time('Taron', 'Black Mamba')} min")