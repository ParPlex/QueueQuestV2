import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
import numpy as np
import importlib

# Forceer reload van route_solver om zeker te zijn dat de nieuwe functies er zijn
import route_solver
importlib.reload(route_solver)

# Nu importeren we de functies uit de ververste module
from route_solver import solve_route_with_priorities, fetch_live_data, get_wait_time_prediction, solve_naive_route
from queuequest_meta import ATTRACTION_METADATA
from holiday_utils import is_crowd_risk_day

st.set_page_config(page_title="QueueQuest Pro", page_icon="🎢", layout="wide")

# --- APP GEHEUGEN ---
if 'completed' not in st.session_state: st.session_state.completed = []
if 'current_loc' not in st.session_state: st.session_state.current_loc = "Ingang"
if 'live_data' not in st.session_state: st.session_state.live_data = {}

st.title("🎢 QueueQuest Ultimate")
st.caption("AI-Powered Route Optimalisatie & Toekomstplanner")

# --- SIDEBAR: SETUP ---
st.sidebar.header("⚙️ Instellingen")
park_keuze = st.sidebar.selectbox("Park:", ("EFTELING", "PHANTASIALAND", "WALIBI_BELGIUM"))

# Filter Rides & Restaurants
all_meta = [name for name, m in ATTRACTION_METADATA.items() if m['park'] == park_keuze]
rides = sorted([r for r in all_meta if ATTRACTION_METADATA[r].get('type') != 'Restaurant' and "Single-rider" not in r])
restaurants = sorted([r for r in all_meta if ATTRACTION_METADATA[r].get('type') in ['Restaurant', 'Snack']])

# 1. Startpunt
st.sidebar.subheader("📍 Huidige Status")
loc_options = ["Ingang"] + rides + restaurants
try:
    default_idx = loc_options.index(st.session_state.current_loc)
except ValueError:
    default_idx = 0
start_loc_select = st.sidebar.selectbox("Waar ben je nu?", loc_options, index=default_idx)
if start_loc_select != st.session_state.current_loc:
    st.session_state.current_loc = start_loc_select

# 2. Selectie (AANGEPAST: We gebruiken keys voor directe manipulatie)
st.sidebar.subheader("🎯 Jouw Wensenlijst")

# We tonen gewoon ALLE rides in de opties, zodat de widget niet crasht/reset
# De filtering gebeurt nu door items uit de 'key' te verwijderen bij het afvinken
must_haves = st.sidebar.multiselect("Must-Haves", rides, key="must_haves_list")

# Voor should haves filteren we wat al in must haves zit om dubbelingen te voorkomen
remaining_options = [r for r in rides if r not in must_haves]
should_haves = st.sidebar.multiselect("Opvulling", remaining_options, key="should_haves_list")

# Live Data Knop
if st.sidebar.button("🔄 Ververs Live Data"):
    try:
        st.session_state.live_data = fetch_live_data(park_keuze)
    except:
        pass
live_data = st.session_state.get('live_data', {})

# Toon storingen
target_rides = must_haves + should_haves
closed_now = [r for r in target_rides if r in live_data and not live_data[r]['is_open']]
if closed_now: st.sidebar.error(f"⛔ Nu Gesloten: {', '.join(closed_now)}")

# --- TABS ---
tab_copilot, tab_best_times, tab_future, tab_done = st.tabs(["📍 Live Co-Piloot", "📊 Beste Tijden", "📅 Toekomst", "✅ Voltooid"])

# ==============================================================================
# TAB 1: LIVE CO-PILOOT
# ==============================================================================
with tab_copilot:
    c1, c2 = st.columns(2)
    start_t = c1.time_input("Tijd Nu", datetime.datetime.now().time())
    end_t = c2.time_input("Einde Dag", datetime.time(18, 0))
    
    if st.button("🚀 Bereken Route vanaf Huidige Locatie", type="primary"):
        if not must_haves and not should_haves:
            st.warning("Kies eerst attracties in de zijbalk.")
        else:
            with st.spinner("AI berekent route..."):
                s_str = start_t.strftime("%H:%M")
                e_str = end_t.strftime("%H:%M")
                
                route, closed, skipped = solve_route_with_priorities(
                    park_keuze, must_haves, should_haves, s_str, e_str, 
                    start_location=st.session_state.current_loc
                )
                st.session_state.last_route = route
                st.session_state.last_closed = closed

    # Toon Route
    if 'last_route' in st.session_state and st.session_state.last_route:
        route = st.session_state.last_route
        if st.session_state.last_closed: st.error(f"⛔ Gesloten: {', '.join(st.session_state.last_closed)}")

        for i, step in enumerate(route):
            # Eerste item altijd open, rest dicht voor rustig overzicht
            is_next = (i == 0)
            label = f"**{step['start_walk']}** | Ga naar **{step['ride']}**"
            if is_next: label = "👉 " + label

            with st.expander(label, expanded=is_next):
                c1, c2, c3 = st.columns([2,2,1])
                c1.write(f"🚶 **Loop:** {step['walk_min']} min")
                c1.write(f"⏳ **Wacht:** {step['wait_min']} min")
                c2.info(f"Status: {step['note']}")
                if step['type'] == "MUST": c2.write("⭐ Prioriteit")
                
                # AFVINKEN LOGICA (AANGEPAST)
                if c3.button("✅ Gedaan!", key=f"done_{step['ride']}_{i}"):
                    ride_done = step['ride']
                    
                    # 1. Voeg toe aan voltooid
                    st.session_state.completed.append(ride_done)
                    
                    # 2. Update locatie
                    st.session_state.current_loc = ride_done
                    
                    # 3. VERWIJDER UIT DE SELECTIELIJSTEN (Dit fixt jouw probleem)
                    if ride_done in st.session_state.must_haves_list:
                        st.session_state.must_haves_list.remove(ride_done)
                    
                    if ride_done in st.session_state.should_haves_list:
                        st.session_state.should_haves_list.remove(ride_done)
                    
                    # 4. Reset route en herlaad
                    if 'last_route' in st.session_state:
                        del st.session_state.last_route
                    st.rerun()

    elif 'last_route' in st.session_state:
        st.success("🎉 Je hebt alles gedaan voor vandaag!")

# ==============================================================================
# TAB 2: BESTE TIJDEN
# ==============================================================================
with tab_best_times:
    st.subheader("🔍 Flexibiliteits-Check")
    
    # Gebruik de huidige selectie
    target_rides = must_haves + should_haves
    if not target_rides:
        st.info("Selecteer attracties in de zijbalk.")
    else:
        now = datetime.datetime.now()
        sh = now.hour if now.hour >= 10 else 10
        eh = 19
        scan_data = []
        
        for ride in target_rides:
            best_h = -1
            min_w = 999
            for h in range(sh, eh):
                t = now.replace(hour=h, minute=0, second=0)
                w = get_wait_time_prediction(park_keuze, ride, t, live_data)
                if isinstance(w, dict): w = 15
                if w < min_w:
                    min_w = w
                    best_h = h
            
            advies = "Nu doen!" if best_h == now.hour else f"Wacht tot {best_h}:00"
            scan_data.append({"Attractie": ride, "Beste Tijd": f"{best_h}:00", "Min. Wacht": f"{min_w} min", "Advies": advies})
            
        st.dataframe(pd.DataFrame(scan_data), use_container_width=True, hide_index=True)

# ==============================================================================
# TAB 3: PLAN JE BEZOEK (TOEKOMST)
# ==============================================================================
with tab_future:
    st.subheader("🔮 Voorspel de toekomst")
    c1, c2 = st.columns(2)
    future_date = c1.date_input("Datum:", datetime.date.today() + datetime.timedelta(days=1))
    weather_forecast = c2.selectbox("Verwacht weer:", ("Zonnig", "Bewolkt", "Regen"))
    
    target_rides = must_haves + should_haves
    if target_rides and st.button("🔮 Voorspel"):
        is_holiday = is_crowd_risk_day(future_date)
        st.info(f"📅 **{future_date.strftime('%d-%m-%Y')}** | Vakantie: {'Ja' if is_holiday else 'Nee'}")

        chart_data = []
        for ride in target_rides:
            for h in range(10, 19):
                sim_time = datetime.datetime.combine(future_date, datetime.time(h, 0))
                w = get_wait_time_prediction(park_keuze, ride, sim_time)
                if isinstance(w, dict): w = 15
                if weather_forecast == "Regen":
                    meta = ATTRACTION_METADATA.get(ride, {})
                    if meta.get('is_indoor') == 0: w = int(w * 0.6)
                    else: w = int(w * 1.3)
                chart_data.append({"Uur": f"{h}:00", "Attractie": ride, "Wachttijd": w})

        fig = px.line(pd.DataFrame(chart_data), x="Uur", y="Wachttijd", color="Attractie", markers=True)
        st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# TAB 4: VOLTOOID
# ==============================================================================
with tab_done:
    if st.session_state.completed:
        st.success(f"Al {len(st.session_state.completed)} gedaan!")
        for r in st.session_state.completed: st.write(f"✅ {r}")
        if st.button("🗑️ Reset Alles"):
            st.session_state.completed = []
            st.session_state.must_haves_list = [] # Reset ook selecties
            st.session_state.should_haves_list = []
            st.session_state.current_loc = "Ingang"
            st.rerun()
    else:
        st.info("Nog niks gedaan.")
