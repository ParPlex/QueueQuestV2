# queuequest_meta.py

# Theoretical Capacity (Cap) = Personen per uur
# lat, lon = Exacte GPS locatie van de ingang
# type = 'Restaurant' (Sit-down/Self-service) of 'Snack' (Afhaal)
# score = 'Fun Factor' (1-10) voor de 'Perfecte Route' algoritme

ATTRACTION_METADATA = {
    # ========================================================
    # 🇳🇱 DE EFTELING
    # ========================================================
    # --- RIDES ---
    "Baron 1898":           {"park": "EFTELING", "type": "Coaster", "zone": "Ruigrijk", "is_indoor": 0, "score": 10, "capacity": 1000, "duration_min": 5, "lat": 51.6492, "lon": 5.0503},
    "Python":               {"park": "EFTELING", "type": "Coaster", "zone": "Ruigrijk", "is_indoor": 0, "score": 7, "capacity": 1400, "duration_min": 4, "lat": 51.6483, "lon": 5.0515},
    "Joris en de Draak":    {"park": "EFTELING", "type": "Coaster", "zone": "Ruigrijk", "is_indoor": 0, "score": 10, "capacity": 1700, "duration_min": 4, "lat": 51.6478, "lon": 5.0510},
    "De Vliegende Hollander":{"park": "EFTELING", "type": "WaterCoaster", "zone": "Ruigrijk", "is_indoor": 0, "score": 9, "capacity": 1900, "duration_min": 6, "lat": 51.6475, "lon": 5.0505},
    "Halve Maen":           {"park": "EFTELING", "type": "FlatRide", "zone": "Ruigrijk", "is_indoor": 0, "score": 5, "capacity": 1200, "duration_min": 5, "lat": 51.6488, "lon": 5.0495},
    "Symbolica":            {"park": "EFTELING", "type": "DarkRide", "zone": "Fantasierijk", "is_indoor": 1, "score": 10, "capacity": 1400, "duration_min": 10, "lat": 51.6508, "lon": 5.0478},
    "Droomvlucht":          {"park": "EFTELING", "type": "DarkRide", "zone": "Marerijk", "is_indoor": 1, "score": 9, "capacity": 1800, "duration_min": 8, "lat": 51.6503, "lon": 5.0435},
    "Villa Volta":          {"park": "EFTELING", "type": "Madhouse", "zone": "Marerijk", "is_indoor": 1, "score": 7, "capacity": 1200, "duration_min": 10, "lat": 51.6500, "lon": 5.0438},
    "Danse Macabre":        {"park": "EFTELING", "type": "DarkRide", "zone": "Anderrijk", "is_indoor": 1, "score": 10, "capacity": 1250, "duration_min": 10, "lat": 51.6470, "lon": 5.0465},
    "Fata Morgana":         {"park": "EFTELING", "type": "DarkRide", "zone": "Anderrijk", "is_indoor": 1, "score": 8, "capacity": 1800, "duration_min": 10, "lat": 51.6465, "lon": 5.0445},
    "Piraña":               {"park": "EFTELING", "type": "WaterRide", "zone": "Anderrijk", "is_indoor": 0, "score": 7, "capacity": 2000, "duration_min": 8, "lat": 51.6480, "lon": 5.0450},
    "Max & Moritz":         {"park": "EFTELING", "type": "Coaster", "zone": "Anderrijk", "is_indoor": 0, "score": 6, "capacity": 1800, "duration_min": 4, "lat": 51.6485, "lon": 5.0460},
    "Vogel Rok":            {"park": "EFTELING", "type": "Coaster", "zone": "Reizenrijk", "is_indoor": 1, "score": 7, "capacity": 1600, "duration_min": 4, "lat": 51.6520, "lon": 5.0485},
    "Carnaval Festival":    {"park": "EFTELING", "type": "DarkRide", "zone": "Reizenrijk", "is_indoor": 1, "score": 6, "capacity": 1600, "duration_min": 8, "lat": 51.6525, "lon": 5.0490},
    "Sirocco":              {"park": "EFTELING", "type": "FlatRide", "zone": "Reizenrijk", "is_indoor": 0, "score": 5, "capacity": 1000, "duration_min": 4, "lat": 51.6530, "lon": 5.0480},
    "Pagode":               {"park": "EFTELING", "type": "Tower",    "zone": "Reizenrijk", "is_indoor": 0, "score": 5, "capacity": 720,  "duration_min": 10, "lat": 51.6510, "lon": 5.0490},
    "Gondoletta":           {"park": "EFTELING", "type": "BoatRide", "zone": "Reizenrijk", "is_indoor": 0, "score": 4, "capacity": 720,  "duration_min": 20, "lat": 51.6515, "lon": 5.0485},

    # --- RESTAURANTS (EFTELING) ---
    "Polles Keuken":        {"park": "EFTELING", "type": "Restaurant", "zone": "Fantasierijk", "lat": 51.6509, "lon": 5.0477},
    "Het Wapen van Raveleijn": {"park": "EFTELING", "type": "Restaurant", "zone": "Marerijk", "lat": 51.6495, "lon": 5.0440},
    "Pinokkio's":           {"park": "EFTELING", "type": "Restaurant", "zone": "Marerijk", "lat": 51.6507, "lon": 5.0438},
    "Station de Oost":      {"park": "EFTELING", "type": "Snack", "zone": "Ruigrijk", "lat": 51.6480, "lon": 5.0500},
    "Frau Boltes Küche":    {"park": "EFTELING", "type": "Snack", "zone": "Anderrijk", "lat": 51.6483, "lon": 5.0462},
    "Fabula Restaurant":    {"park": "EFTELING", "type": "Snack", "zone": "Anderrijk", "lat": 51.6490, "lon": 5.0465},
    "Kashba":               {"park": "EFTELING", "type": "Restaurant", "zone": "Reizenrijk", "lat": 51.6518, "lon": 5.0482},
    "Bäckerei Krümel":      {"park": "EFTELING", "type": "Snack", "zone": "Anderrijk", "lat": 51.6484, "lon": 5.0458},
    "In de Gelaarsde Kat":  {"park": "EFTELING", "type": "Snack", "zone": "Marerijk", "lat": 51.6502, "lon": 5.0415}, 

    # ========================================================
    # 🇩🇪 PHANTASIALAND
    # ========================================================
    # --- RIDES ---
    "Taron":                {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Klugheim", "is_indoor": 0, "score": 10, "capacity": 1200, "duration_min": 4, "lat": 50.7996, "lon": 6.8828},
    "Raik":                 {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Klugheim", "is_indoor": 0, "score": 6, "capacity": 700, "duration_min": 3, "lat": 50.7997, "lon": 6.8830},
    "Black Mamba":          {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Deep in Africa", "is_indoor": 0, "score": 9, "capacity": 1500, "duration_min": 4, "lat": 50.7990, "lon": 6.8805},
    "F.L.Y.":               {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Rookburgh", "is_indoor": 0, "score": 10, "capacity": 1400, "duration_min": 5, "lat": 50.8000, "lon": 6.8795},
    "Maus au Chocolat":     {"park": "PHANTASIALAND", "type": "DarkRide", "zone": "Berlin", "is_indoor": 1, "score": 9, "capacity": 1200, "duration_min": 8, "lat": 50.8001, "lon": 6.8790},
    "Wellenflug":           {"park": "PHANTASIALAND", "type": "FlatRide", "zone": "Berlin", "is_indoor": 0, "score": 5, "capacity": 800, "duration_min": 4, "lat": 50.8002, "lon": 6.8792},
    "Chiapas":              {"park": "PHANTASIALAND", "type": "WaterRide", "zone": "Mexico", "is_indoor": 0, "score": 9, "capacity": 1800, "duration_min": 7, "lat": 50.7993, "lon": 6.8823},
    "Talocan":              {"park": "PHANTASIALAND", "type": "FlatRide", "zone": "Mexico", "is_indoor": 0, "score": 8, "capacity": 900, "duration_min": 4, "lat": 50.7994, "lon": 6.8820},
    "Colorado Adventure":   {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Mexico", "is_indoor": 0, "score": 8, "capacity": 1800, "duration_min": 5, "lat": 50.7990, "lon": 6.8830},
    "River Quest":          {"park": "PHANTASIALAND", "type": "WaterRide", "zone": "Mystery", "is_indoor": 0, "score": 8, "capacity": 800,  "duration_min": 6, "lat": 50.8000, "lon": 6.8841},
    "Mystery Castle":       {"park": "PHANTASIALAND", "type": "Tower", "zone": "Mystery", "is_indoor": 1, "score": 8, "capacity": 600,  "duration_min": 5, "lat": 50.8002, "lon": 6.8843},
    "Winja's Fear":         {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Wuze Town", "is_indoor": 1, "score": 7, "capacity": 700, "duration_min": 4, "lat": 50.8005, "lon": 6.8780},
    "Winja's Force":        {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Wuze Town", "is_indoor": 1, "score": 7, "capacity": 700, "duration_min": 4, "lat": 50.8005, "lon": 6.8780},
    "Crazy Bats":           {"park": "PHANTASIALAND", "type": "VR Coaster", "zone": "Fantasy", "is_indoor": 1, "score": 4, "capacity": 1000, "duration_min": 6, "lat": 50.8008, "lon": 6.8775},

    # --- RESTAURANTS (PHANTASIALAND) ---
    "Uhrwerk":              {"park": "PHANTASIALAND", "type": "Restaurant", "zone": "Rookburgh", "lat": 50.8001, "lon": 6.8794},
    "Rutmor's Taverne":     {"park": "PHANTASIALAND", "type": "Restaurant", "zone": "Klugheim", "lat": 50.7995, "lon": 6.8829},
    "Manchu":               {"park": "PHANTASIALAND", "type": "Restaurant", "zone": "China Town", "lat": 50.7992, "lon": 6.8835},
    "Cocorico":             {"park": "PHANTASIALAND", "type": "Restaurant", "zone": "Mexico", "lat": 50.7993, "lon": 6.8825},
    "Unter den Linden":     {"park": "PHANTASIALAND", "type": "Restaurant", "zone": "Berlin", "lat": 50.8002, "lon": 6.8792},

    # ========================================================
    # 🇧🇪 WALIBI BELGIUM
    # ========================================================
    # --- RIDES ---
    "Kondaa":               {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Exotic World", "is_indoor": 0, "score": 10, "capacity": 1200, "duration_min": 4, "lat": 50.6970, "lon": 4.5840},
    "Tiki-Waka":            {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Exotic World", "is_indoor": 0, "score": 6, "capacity": 800, "duration_min": 3, "lat": 50.6975, "lon": 4.5855},
    "Challenge of Tutankhamon": {"park": "WALIBI_BELGIUM", "type": "DarkRide", "zone": "Exotic World", "is_indoor": 1, "score": 8, "capacity": 900, "duration_min": 6, "lat": 50.6978, "lon": 4.5860},
    "PULSAR":               {"park": "WALIBI_BELGIUM", "type": "WaterCoaster", "zone": "Dock World", "is_indoor": 0, "score": 9, "capacity": 850, "duration_min": 3, "lat": 50.6988, "lon": 4.5903},
    "Psyké Underground":    {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Dock World", "is_indoor": 1, "score": 8, "capacity": 600, "duration_min": 3, "lat": 50.6985, "lon": 4.5910},
    "Flash Back":           {"park": "WALIBI_BELGIUM", "type": "WaterRide", "zone": "Dock World", "is_indoor": 0, "score": 7, "capacity": 1000, "duration_min": 7, "lat": 50.6990, "lon": 4.5915},
    "Cobra":                {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Karma World", "is_indoor": 0, "score": 5, "capacity": 700, "duration_min": 3, "lat": 50.7005, "lon": 4.5941},
    "Radja River":          {"park": "WALIBI_BELGIUM", "type": "WaterRide", "zone": "Karma World", "is_indoor": 0, "score": 7, "capacity": 1400, "duration_min": 7, "lat": 50.7000, "lon": 4.5950},
    "Popcorn Revenge":      {"park": "WALIBI_BELGIUM", "type": "DarkRide", "zone": "Karma World", "is_indoor": 1, "score": 7, "capacity": 600, "duration_min": 6, "lat": 50.7008, "lon": 4.5945},
    "Weerwolf":             {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Fun World", "is_indoor": 0, "score": 8, "capacity": 1000, "duration_min": 4, "lat": 50.7008, "lon": 4.5902},
    "Vampire":              {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Dock World", "is_indoor": 0, "score": 6, "capacity": 800, "duration_min": 3, "lat": 50.6995, "lon": 4.5890},
    "Dalton Terror":        {"park": "WALIBI_BELGIUM", "type": "Tower", "zone": "Wild West", "is_indoor": 0, "score": 7, "capacity": 600, "duration_min": 3, "lat": 50.6990, "lon": 4.5874},
    "Calamity Mine":        {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Wild West", "is_indoor": 0, "score": 7, "capacity": 1000, "duration_min": 4, "lat": 50.6985, "lon": 4.5870},

    # --- RESTAURANTS (WALIBI) ---
    "Country Cantina":      {"park": "WALIBI_BELGIUM", "type": "Restaurant", "zone": "Wild West", "lat": 50.6990, "lon": 4.5880},
    "Delhi'cious":          {"park": "WALIBI_BELGIUM", "type": "Restaurant", "zone": "Karma World", "lat": 50.7006, "lon": 4.5943},
    "Nsoso":                {"park": "WALIBI_BELGIUM", "type": "Restaurant", "zone": "Exotic World", "lat": 50.6975, "lon": 4.5850},
}