# queuequest_meta.py

# Theoretical Capacity (Cap) = Personen per uur (geschat)
# is_indoor: 1 = Binnen (Weeronafhankelijk), 0 = Buiten (Gevoelig voor regen)
# duration_min: Geschatte totale tijd van de ervaring (rit + voorshow + uitstappen)

ATTRACTION_METADATA = {
    # ========================================================
    # 🇳🇱 DE EFTELING (Kaatsheuvel, NL)
    # ========================================================
    "Baron 1898":               {"park": "EFTELING", "type": "Coaster", "zone": "Ruigrijk", "is_indoor": 0, "capacity": 1000, "duration_min": 5},
    "Baron 1898 Single-rider":  {"park": "EFTELING", "type": "Coaster", "zone": "Ruigrijk", "is_indoor": 0, "capacity": 1000, "duration_min": 5},
    "Python":                   {"park": "EFTELING", "type": "Coaster", "zone": "Ruigrijk", "is_indoor": 0, "capacity": 1400, "duration_min": 4},
    "Joris en de Draak":        {"park": "EFTELING", "type": "Coaster", "zone": "Ruigrijk", "is_indoor": 0, "capacity": 1700, "duration_min": 4},
    "De Vliegende Hollander":   {"park": "EFTELING", "type": "WaterCoaster", "zone": "Ruigrijk", "is_indoor": 0, "capacity": 1900, "duration_min": 6},
    "Symbolica":                {"park": "EFTELING", "type": "DarkRide", "zone": "Fantasierijk", "is_indoor": 1, "capacity": 1400, "duration_min": 10},
    "Droomvlucht":              {"park": "EFTELING", "type": "DarkRide", "zone": "Marerijk", "is_indoor": 1, "capacity": 1800, "duration_min": 8},
    "Danse Macabre":            {"park": "EFTELING", "type": "DarkRide", "zone": "Anderrijk", "is_indoor": 1, "capacity": 1250, "duration_min": 10}, # Incl voorshow
    "Fata Morgana":             {"park": "EFTELING", "type": "DarkRide", "zone": "Anderrijk", "is_indoor": 1, "capacity": 1800, "duration_min": 10},
    "Piraña":                   {"park": "EFTELING", "type": "WaterRide", "zone": "Anderrijk", "is_indoor": 0, "capacity": 2000, "duration_min": 8},
    "Max & Moritz":             {"park": "EFTELING", "type": "Coaster", "zone": "Anderrijk", "is_indoor": 0, "capacity": 1800, "duration_min": 4},
    "Vogel Rok":                {"park": "EFTELING", "type": "Coaster", "zone": "Reizenrijk", "is_indoor": 1, "capacity": 1600, "duration_min": 4},
    "Carnaval Festival":        {"park": "EFTELING", "type": "DarkRide", "zone": "Reizenrijk", "is_indoor": 1, "capacity": 1600, "duration_min": 8},
    "Villa Volta":              {"park": "EFTELING", "type": "Madhouse", "zone": "Marerijk", "is_indoor": 1, "capacity": 1200, "duration_min": 10}, # Voorshows duren lang
    "Sirocco":                  {"park": "EFTELING", "type": "FlatRide", "zone": "Reizenrijk", "is_indoor": 0, "capacity": 1000, "duration_min": 4},
    "Halve Maen":               {"park": "EFTELING", "type": "FlatRide", "zone": "Ruigrijk", "is_indoor": 0, "capacity": 1200, "duration_min": 5},
    "Pagode":                   {"park": "EFTELING", "type": "Tower",    "zone": "Reizenrijk", "is_indoor": 0, "capacity": 720,  "duration_min": 10}, # Laden duurt lang
    "Gondoletta":               {"park": "EFTELING", "type": "BoatRide", "zone": "Reizenrijk", "is_indoor": 0, "capacity": 720,  "duration_min": 20}, # Lange rit!
    
    # ========================================================
    # 🇩🇪 PHANTASIALAND (Brühl, DE)
    # ========================================================
    "Taron":                    {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Klugheim", "is_indoor": 0, "capacity": 1200, "duration_min": 4},
    "Raik":                     {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Klugheim", "is_indoor": 0, "capacity": 700, "duration_min": 3},
    "Black Mamba":              {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Deep in Africa", "is_indoor": 0, "capacity": 1500, "duration_min": 4},
    "F.L.Y.":                   {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Rookburgh", "is_indoor": 0, "capacity": 1400, "duration_min": 5}, # Lang in/uitstappen
    "Colorado Adventure":       {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Mexico", "is_indoor": 0, "capacity": 1800, "duration_min": 5},
    "Chiapas":                  {"park": "PHANTASIALAND", "type": "WaterRide", "zone": "Mexico", "is_indoor": 0, "capacity": 1800, "duration_min": 7},
    "River Quest":              {"park": "PHANTASIALAND", "type": "WaterRide", "zone": "Mystery", "is_indoor": 0, "capacity": 800,  "duration_min": 6},
    "Mystery Castle":           {"park": "PHANTASIALAND", "type": "Tower", "zone": "Mystery", "is_indoor": 1, "capacity": 600,  "duration_min": 5},
    "Maus au Chocolat":         {"park": "PHANTASIALAND", "type": "DarkRide", "zone": "Berlin", "is_indoor": 1, "capacity": 1200, "duration_min": 8},
    "Winja's Fear":             {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Wuze Town", "is_indoor": 1, "capacity": 700, "duration_min": 4},
    "Winja's Force":            {"park": "PHANTASIALAND", "type": "Coaster", "zone": "Wuze Town", "is_indoor": 1, "capacity": 700, "duration_min": 4},
    "Crazy Bats":               {"park": "PHANTASIALAND", "type": "VR Coaster", "zone": "Fantasy", "is_indoor": 1, "capacity": 1000, "duration_min": 6},
    "Talocan":                  {"park": "PHANTASIALAND", "type": "FlatRide", "zone": "Mexico", "is_indoor": 0, "capacity": 900, "duration_min": 4},
    "Feng Ju Palace":           {"park": "PHANTASIALAND", "type": "Madhouse", "zone": "China Town", "is_indoor": 1, "capacity": 800, "duration_min": 8},
    "Geister Rikscha":          {"park": "PHANTASIALAND", "type": "DarkRide", "zone": "China Town", "is_indoor": 1, "capacity": 1600, "duration_min": 9},
    "Wellenflug":               {"park": "PHANTASIALAND", "type": "FlatRide", "zone": "Berlin", "is_indoor": 0, "capacity": 800, "duration_min": 4},

    # ========================================================
    # 🇧🇪 WALIBI BELGIUM (Waver, BE)
    # ========================================================
    "Kondaa":                   {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Exotic World", "is_indoor": 0, "capacity": 1200, "duration_min": 4},
    "PULSAR":                   {"park": "WALIBI_BELGIUM", "type": "WaterCoaster", "zone": "Dock World", "is_indoor": 0, "capacity": 850, "duration_min": 3},
    "Psyké Underground":        {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Dock World", "is_indoor": 1, "capacity": 600, "duration_min": 3},
    "Flash Back":               {"park": "WALIBI_BELGIUM", "type": "WaterRide", "zone": "Dock World", "is_indoor": 0, "capacity": 1000, "duration_min": 7},
    "Cobra":                    {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Karma World", "is_indoor": 0, "capacity": 700, "duration_min": 3},
    "Popcorn Revenge":          {"park": "WALIBI_BELGIUM", "type": "DarkRide", "zone": "Karma World", "is_indoor": 1, "capacity": 600, "duration_min": 6},
    "Radja River":              {"park": "WALIBI_BELGIUM", "type": "WaterRide", "zone": "Karma World", "is_indoor": 0, "capacity": 1400, "duration_min": 7},
    "Loup-Garou":               {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Fun World", "is_indoor": 0, "capacity": 1000, "duration_min": 4},
    "Vampire":                  {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Dock World", "is_indoor": 0, "capacity": 800, "duration_min": 3},
    "Dalton Terror":            {"park": "WALIBI_BELGIUM", "type": "Tower", "zone": "Wild West", "is_indoor": 0, "capacity": 600, "duration_min": 3},
    "Challenge of Tutankhamon": {"park": "WALIBI_BELGIUM", "type": "DarkRide", "zone": "Exotic World", "is_indoor": 1, "capacity": 900, "duration_min": 6},
    "Tiki-Waka":                {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Exotic World", "is_indoor": 0, "capacity": 800, "duration_min": 3},
    "Calamity Mine":            {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Wild West", "is_indoor": 0, "capacity": 1000, "duration_min": 4},
    "Fun Pilot":                {"park": "WALIBI_BELGIUM", "type": "Coaster", "zone": "Fun World", "is_indoor": 0, "capacity": 600, "duration_min": 2},
}