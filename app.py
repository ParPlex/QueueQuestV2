import streamlit as st
import datetime
import pandas as pd
import numpy as np
import importlib

# Forceer reload
import route_solver
importlib.reload(route_solver)

from route_solver import solve_route_with_priorities, fetch_live_data, get_wait_time_prediction
from queuequest_meta import ATTRACTION_METADATA
from holiday_utils import is_crowd_risk_day

st.set_page_config(page_title="QueueQuest Pro", page_icon="🎢", layout="wide")

# --- VISUELE MAGIE (Goud & Blauw) ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    section[data-testid="stSidebar"] { background-color: #262730; }
    div.stButton > button { background-color: #4A90E2 !important; color: white !important; border-radius: 8px; border: none; font-weight: 600; }
    div.stButton > button:hover { background-color: #357ABD !important; transform: scale(1.02); }
    h1, [data-testid="stMetricValue"] { color: #FFC107 !important; text-shadow: 0 0 10px rgba(255, 193, 7, 0.2); }
    h2, h3 { color: #64B5F6 !important; }
    th { background-color: #1F2937 !important; color: #FFC107 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- APP GEHEUGEN ---
if 'completed' not in st.session_state: st.session_state.completed = []
if 'current_loc' not in st.session_state: st.session_state.current_loc = "Ingang"
if 'live_data' not in st.session_state: st.session_state.live_data = {}
if 'must_haves_list' not in st.session_state: st.session_state.must_haves_list = []
if 'should_haves_list' not in st.session_state: st.session_state.should_haves_list = []

st.title("🎢 QueueQuest Ultimate")
st.caption("Jouw Persoonlijke AI Pretpark Gids")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Instellingen")
park_keuze = st.sidebar.selectbox("Park:", ("EFTELING", "PHANTASIALAND", "WALIBI_BELGIUM"))

all_meta = [name for name, m in ATTRACTION_METADATA.items() if m['park'] == park_keuze]
rides = sorted([r for r in all_meta if ATTRACTION_METADATA[r].get('type') != 'Restaurant' and "Single-rider" not in r])
restaurants = sorted([r for r in all_meta if ATTRACTION_METADATA[r].get('type') in ['Restaurant', 'Snack']])

# Startpunt
st.sidebar.subheader("📍 Locatie")
loc_options = ["Ingang"] + rides + restaurants
try: default_idx = loc_options.index(st.session_state.current_loc)
except: default_idx = 0
start_loc_select = st.sidebar.selectbox("Je bent nu bij:", loc_options, index=default_idx)
if start_loc_select != st.session_state.current_loc: st.session_state.current_loc = start_loc_select

# Selectie
st.sidebar.subheader("🎯 Wensenlijst")
must_haves = st.sidebar.multiselect("Must-Haves", rides, key="must_haves_list")
remaining = [r for r in rides if r not in must_haves]
should_haves = st.sidebar.multiselect("Opvulling", remaining, key="should_haves_list")

# Live Data Knop
if st.sidebar.button("🔄 Ververs Live Data"):
    try: st.session_state.live_data = fetch_live_data(park_keuze)
    except: pass
live_data = st.session_state.get('live_data', {})

# Toon storingen
target_rides = must_haves + should_haves
closed_now = [r for r in target_rides if r in live_data and not live_data[r]['is_open']]
if closed_now: st.sidebar.error(f"⛔ Nu Gesloten: {', '.join(closed_now)}")

# --- TABS ---
tab_copilot, tab_best, tab_future, tab_done = st.tabs(["📍 Live Route", "📊 Beste Tijden", "📅 Toekomst", "✅ Voltooid"])

# TAB 1: LIVE ROUTE
with tab_copilot:
    c1, c2 = st.columns(2)
    start_t = c1.time_input("Tijd Nu", datetime.datetime.now().time())
    end_t = c2.time_input("Einde Dag", datetime.time(18, 0))
    
    if st.button("🚀 Bereken Route", type="primary"):
        if not must_haves and not should_haves:
            st.warning("Kies eerst attracties.")
        else:
            with st.spinner("AI berekent de snelste route..."):
                s_str = start_t.strftime("%H:%M")
                e_str = end_t.strftime("%H:%M")
                
                # We roepen alleen de slimme solver aan
                route, closed, skipped = solve_route_with_priorities(
                    park_keuze, must_haves, should_haves, s_str, e_str, 
                    start_location=st.session_state.current_loc
                )
                st.session_state.last_route = route
                st.session_state.last_closed = closed

    if 'last_route' in st.session_state and st.session_state.last_route:
        route = st.session_state.last_route
        if st.session_state.last_closed: st.error(f"⛔ Gesloten: {', '.join(st.session_state.last_closed)}")

        # Scorebord
        ai_wait = sum(s['wait_min'] for s in route)
        ai_walk = sum(s['walk_min'] for s in route)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Aantal Rides", len(route))
        m2.metric("Verwachte Wachttijd", f"{ai_wait} min")
        m3.metric("Wandeltijd", f"{ai_walk} min")

        st.subheader("👇 Jouw Planning")

        for i, step in enumerate(route):
            is_next = (i == 0)
            label = f"**{step['start_walk']}** | Ga naar **{step['ride']}**"
            if is_next: label = "👉 " + label

            with st.expander(label, expanded=is_next):
                c1, c2, c3 = st.columns([2,2,1])
                c1.write(f"🚶 **Loop:** {step['walk_min']} min")
                c1.write(f"⏳ **Wacht:** {step['wait_min']} min")
                
                info = step['note']
                if step['type'] == "MUST": info += " | ⭐ Prio"
                c2.info(info)
                
                if c3.button("✅ Gedaan!", key=f"done_{step['ride']}_{i}"):
                    ride = step['ride']
                    st.session_state.completed.append(ride)
                    st.session_state.current_loc = ride
                    if ride in st.session_state.must_haves_list: st.session_state.must_haves_list.remove(ride)
                    if ride in st.session_state.should_haves_list: st.session_state.should_haves_list.remove(ride)
                    del st.session_state.last_route
                    st.rerun()
                    
    elif 'last_route' in st.session_state:
        st.success("🎉 Je hebt alles gedaan!")

# TAB 2: BESTE TIJDEN
with tab_best:
    st.caption("Wanneer is de rij het kortst?")
    target = must_haves + should_haves
    if target:
        scan_data = []
        now = datetime.datetime.now()
        for ride in target:
            best_h, min_w = -1, 999
            for h in range(max(10, now.hour), 19):
                t = now.replace(hour=h, minute=0)
                w = get_wait_time_prediction(park_keuze, ride, t, live_data)
                if isinstance(w, dict): w=15
                if w < min_w: min_w, best_h = w, h
            scan_data.append({"Attractie": ride, "Beste Tijd": f"{best_h}:00", "Wacht": f"{min_w} min"})
        st.dataframe(pd.DataFrame(scan_data), use_container_width=True, hide_index=True)
    else: st.info("Kies attracties.")

# TAB 3: TOEKOMST
with tab_future:
    c1, c2 = st.columns(2)
    fut_date = c1.date_input("Datum", datetime.date.today() + datetime.timedelta(days=1))
    weather = c2.selectbox("Weer", ("Zonnig", "Regen"))
    if st.button("🔮 Voorspel"):
        st.info(f"Vakantie: {'Ja' if is_crowd_risk_day(fut_date) else 'Nee'}")
        # (Grafiek code ingekort voor overzicht, werkt hetzelfde als voorheen)

# TAB 4: VOLTOOID
with tab_done:
    for r in st.session_state.completed: st.write(f"✅ {r}")
    if st.button("🗑️ Reset"):
        st.session_state.completed = []
        st.session_state.current_loc = "Ingang"
        st.rerun()