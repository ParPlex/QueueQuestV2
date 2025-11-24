import holidays
import datetime

# --- CONFIGURATIE ---
# We combineren feestdagen van:
# NL = Nederland (Voor Efteling)
# BE = België (Voor Walibi Belgium)
# DE (Subdivisie NW) = Duitsland, Noordrijn-Westfalen (Voor Phantasialand & gasten in NL/BE)

def get_project_holiday_calendar(years=[2023, 2024, 2025, 2026]):
    """
    Genereert een gecombineerde lijst van feestdagen voor Project QueueQuest.
    """
    nl_holidays = holidays.country_holidays('NL', years=years)
    be_holidays = holidays.country_holidays('BE', years=years)
    
    # Phantasialand ligt in Brühl (Noordrijn-Westfalen).
    # Veel Efteling/Walibi bezoekers komen ook uit deze regio.
    de_holidays = holidays.country_holidays('DE', subdiv='NW', years=years)

    # Combineer alle sets. De 'in' operator werkt nu voor al deze dagen.
    combined_holidays = nl_holidays + be_holidays + de_holidays
    return combined_holidays

# Initialiseer de kalender globaal
QUEUEQUEST_HOLIDAYS = get_project_holiday_calendar()

def is_crowd_risk_day(date_obj):
    """
    Geeft 1 terug als de dag een hoog risico heeft op drukte (Weekend of Feestdag in regio).
    """
    # Zorg dat we met een date-object werken
    if isinstance(date_obj, datetime.datetime):
        date_obj = date_obj.date()

    # 1. Weekend Check (Zaterdag=5, Zondag=6)
    if date_obj.weekday() >= 5:
        return 1
    
    # 2. Feestdag Check (NL, BE of DE-NW)
    if date_obj in QUEUEQUEST_HOLIDAYS:
        return 1
    
    return 0

if __name__ == "__main__":
    # Korte test om te zien of het werkt voor alle 3 de landen
    test_dates = [
        (datetime.date(2025, 4, 27), "Koningsdag (NL)"),
        (datetime.date(2025, 7, 21), "Nationale Feestdag (BE)"),
        (datetime.date(2025, 6, 19), "Sacramentsdag (DE-NW & BE, niet NL)"),
        (datetime.date(2025, 11, 24), "Gewone Maandag"),
    ]
    
    print(f"{'Datum':<12} | {'Risk':<5} | {'Test Scenario'}")
    print("-" * 40)
    for d, desc in test_dates:
        print(f"{str(d):<12} | {is_crowd_risk_day(d):<5} | {desc}")