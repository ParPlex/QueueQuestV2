import math
from queuequest_meta import ATTRACTION_METADATA

# --- CONFIGURATIE ---
WALKING_SPEED_KMH = 4.5  
DETOUR_FACTOR = 1.3      # Iets lager gezet omdat we nu preciezer meten

# Back-up coördinaten (voor als een attractie geen GPS heeft)
ZONE_LOCATIONS = {
    "EFTELING": {
        "Ingang": (51.6455, 5.0435), # Huis van de Vijf Zintuigen
        "Marerijk": (51.6505, 5.0425),
        "Ruigrijk": (51.6485, 5.0505),
        "Anderrijk": (51.6475, 5.0460),
        "Reizenrijk": (51.6525, 5.0475),
        "Fantasierijk": (51.6510, 5.0455),
        "Unknown": (51.6500, 5.0450)
    },
    "PHANTASIALAND": {
        "Ingang": (50.8001, 6.8790), # Berlin Ingang
        "Unknown": (50.7998, 6.8810)
    },
    "WALIBI_BELGIUM": {
        "Ingang": (50.7020, 4.5950), 
        "Unknown": (50.6995, 4.5890)
    }
}

def haversine_distance(coord1, coord2):
    """Berekent afstand in meters (vogelvlucht)."""
    R = 6371000 
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_coordinates(park_name, location_name):
    """Probeert de exacte GPS te vinden, anders fallback naar zone."""
    
    # 1. Is het de Ingang?
    if location_name == "Ingang":
        return ZONE_LOCATIONS.get(park_name, {}).get("Ingang")

    # 2. Is het een attractie/restaurant met eigen GPS?
    meta = ATTRACTION_METADATA.get(location_name)
    if meta and "lat" in meta and "lon" in meta:
        return (meta["lat"], meta["lon"])
    
    # 3. Fallback: Zone
    if meta:
        zone = meta.get("zone", "Unknown")
        return ZONE_LOCATIONS.get(park_name, {}).get(zone)
    
    return None

def get_travel_time(loc_a, loc_b):
    """Berekent wandeltijd in minuten."""
    if loc_a == loc_b: return 0
    
    # Probeer park te achterhalen
    meta_a = ATTRACTION_METADATA.get(loc_a)
    meta_b = ATTRACTION_METADATA.get(loc_b)
    
    # Als een van de twee "Ingang" is, moeten we weten welk park
    park_name = meta_a['park'] if meta_a else (meta_b['park'] if meta_b else "EFTELING")
    
    coord_a = get_coordinates(park_name, loc_a)
    coord_b = get_coordinates(park_name, loc_b)
    
    if not coord_a or not coord_b: return 10 # Veilige fallback
    
    dist_meters = haversine_distance(coord_a, coord_b)
    real_dist = dist_meters * DETOUR_FACTOR
    
    speed_m_min = (WALKING_SPEED_KMH * 1000) / 60
    return int(math.ceil(real_dist / speed_m_min))

if __name__ == "__main__":
    print(f"Baron -> Python: {get_travel_time('Baron 1898', 'Python')} min")
    print(f"Ingang -> Droomvlucht: {get_travel_time('Ingang', 'Droomvlucht')} min")