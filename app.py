import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
import numpy as np
import importlib

# Forceer reload van route_solver bij elke interactie
import route_solver
importlib.reload(route_solver)

from route_solver import solve_route_with_priorities, fetch_live_data, get_wait_time_prediction
from queuequest_meta import ATTRACTION_METADATA
from holiday_utils import is_crowd_risk_day

st.set_page_config(page_title="QueueQuest Pro", page_icon="🎢", layout="wide")

# --- CSS STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    section[data-testid="stSidebar"] { background-color: #262730; }
    div.stButton > button { background-color: #4A90E2 !important; color: white !important; border-radius: 8px; border: none; font-weight: 600; }
    div.stButton > button:hover { background-color: #357ABD !important; transform: scale(1.02); }
    h1, [data-testid="stMetricValue"] { color: #FFC107 !important; text-shadow: 0 0 10px rgba(255, 193, 7, 0.2); }
    h2, h3 { color: #64B5F6 !important; }
    th { background-color: #1F2937 !important; color: #FFC107 !important; }
    
    /* Cards styling (gebruikt in Tab 2 en Tab 3) */
    .advice-card {
        background-color: #1F2937; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #FFC107;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: transform 0.2s;
    }
    .advice-card:hover { transform: translateY(-2px); }
    .advice-title { font-weight: bold; font-size: 1.1em; color: white; margin-bottom: 5px; }
    .advice-time { font-size: 1.4em; font-weight: bold; color: #FFC107; }
    .advice-wait { font-size: 0.9em; color: #B0BEC5; }
    
    /* Custom metric box voor gemiddelden */
    .metric-box {
        background-color: #262730; border-radius: 8px; padding: 10px; text-align: center; border: 1px solid #444;
    }
    .metric-val { font-size: 1.5em; font-weight: bold; color: #64B5F6; }
    .metric-lbl { font-size: 0.8em; color: #AAA; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. STATE INITIALISATIE ---
defaults = {
    'completed': [],
    'current_loc': "Ingang",
    'live_data': {},
    'lunch_done': False,
    'last_route': None,
    'last_closed': [],
    'mc': [], 'sc': [], # Coasters
    'md': [], 'sd': [], # Darkrides
    'mo': [], 'so': []  # Overige
}

for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# Tijd State
if 'start_time_val' not in st.session_state:
    now = datetime.datetime.now()
    st.session_state.start_time_val = datetime.time(10, 0) if now.hour < 10 else now.time()
if 'end_time_val' not in st.session_state:
    st.session_state.end_time_val = datetime.time(18, 0)

# --- CALLBACKS ---
def update_start_time(): st.session_state.start_time_val = st.session_state.widget_start_time
def update_end_time(): st.session_state.end_time_val = st.session_state.widget_end_time

def mark_done(ride_name):
    """
    Verwijdert de attractie uit de selecties en update status.
    """
    # 1. Voeg toe aan voltooid
    if ride_name not in st.session_state.completed:
        st.session_state.completed.append(ride_name)
    
    # 2. Update locatie
    st.session_state.current_loc = ride_name
        
    # 3. Wis oude route en update tijd
    st.session_state.last_route = None
    st.session_state.start_time_val = datetime.datetime.now().time()

st.title("🎢 QueueQuest Ultimate")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Instellingen")
park_keuze = st.sidebar.selectbox("Park:", ("EFTELING", "PHANTASIALAND", "WALIBI_BELGIUM"))

all_meta = {k: v for k, v in ATTRACTION_METADATA.items() if v['park'] == park_keuze}
# Stabiele basislijst
rides_all = sorted([r for r, m in all_meta.items() if m.get('type') not in ['Restaurant', 'Snack'] and "Single-rider" not in r])
restaurants = sorted([r for r, m in all_meta.items() if m.get('type') in ['Restaurant', 'Snack']])

# Startpunt
st.sidebar.subheader("📍 Locatie")
loc_options = ["Ingang"] + rides_all + restaurants

# Veiligheidscheck
if st.session_state.current_loc not in loc_options:
    st.session_state.current_loc = "Ingang"

st.sidebar.selectbox("Je bent nu bij:", loc_options, key="current_loc")

# --- SELECTIE ---
st.sidebar.subheader("🎯 Wensenlijst")

# OPSCHONEN: Verwijder voltooide items uit de actieve selectielijsten
keys_to_clean = ['mc', 'sc', 'md', 'sd', 'mo', 'so']
for k in keys_to_clean:
    if st.session_state.completed:
        st.session_state[k] = [x for x in st.session_state[k] if x not in st.session_state.completed]

coasters = [r for r in rides_all if all_meta[r].get('type') in ['Coaster', 'WaterCoaster']]
darkrides = [r for r in rides_all if all_meta[r].get('type') in ['DarkRide', 'Madhouse', 'Cinema']]
others = [r for r in rides_all if r not in coasters and r not in darkrides]

with st.sidebar.expander("🎢 Achtbanen", expanded=True):
    st.multiselect("Must-Haves", coasters, key="mc")
    remain_c = [r for r in coasters if r not in st.session_state.mc]
    st.multiselect("Opvulling", remain_c, key="sc")

with st.sidebar.expander("👻 Darkrides & Shows"):
    st.multiselect("Must-Haves", darkrides, key="md")
    remain_d = [r for r in darkrides if r not in st.session_state.md]
    st.multiselect("Opvulling", remain_d, key="sd")

with st.sidebar.expander("🎡 Overige"):
    st.multiselect("Must-Haves", others, key="mo")
    remain_o = [r for r in others if r not in st.session_state.mo]
    st.multiselect("Opvulling", remain_o, key="so")

must_haves = st.session_state.mc + st.session_state.md + st.session_state.mo
should_haves = st.session_state.sc + st.session_state.sd + st.session_state.so

# Lunch
st.sidebar.markdown("---")
with st.sidebar.expander("🍔 Lunch Pauze"):
    want_lunch = st.checkbox("Inplannen?", value=not st.session_state.lunch_done)
    if want_lunch and not st.session_state.lunch_done:
        l_time = st.time_input("Hoe laat?", datetime.time(12, 30))
        l_dur = st.number_input("Minuten", 15, 120, 45, step=15)
        l_rest = st.selectbox("Waar?", restaurants)
        lunch_config = {'time': l_time, 'duration': l_dur, 'restaurant': l_rest}
    else:
        lunch_config = None
        if st.session_state.lunch_done: st.sidebar.success("Lunch gehad! ✅")

if st.sidebar.button("🔄 Ververs Live Data"):
    try: st.session_state.live_data = fetch_live_data(park_keuze)
    except: pass
live_data = st.session_state.get('live_data', {})

active_selection = must_haves + should_haves
is_park_closed = len(live_data) > 0 and len([r for r in live_data.values() if r['is_open']]) < 3
if not is_park_closed:
    closed_now = [r for r in active_selection if r in live_data and not live_data[r]['is_open']]
    if closed_now: st.sidebar.error(f"⛔ Nu Gesloten: {', '.join(closed_now)}")
else: st.sidebar.info("ℹ️ Park gesloten (Forecast Modus)")

# --- TABS ---
tab_copilot, tab_best, tab_future, tab_done = st.tabs(["📍 Live Route", "📊 Beste Tijden", "📅 Toekomst", "✅ Voltooid"])

# TAB 1: CO-PILOOT
with tab_copilot:
    c1, c2 = st.columns(2)
    c1.time_input("Starttijd", value=st.session_state.start_time_val, key="widget_start_time", on_change=update_start_time)
    c2.time_input("Eindtijd", value=st.session_state.end_time_val, key="widget_end_time", on_change=update_end_time)
    
    if st.button("🚀 Bereken Route", type="primary"):
        if not active_selection and not lunch_config:
            st.warning("Kies eerst attracties.")
        else:
            with st.spinner("AI berekent route..."):
                s_str = st.session_state.start_time_val.strftime("%H:%M")
                e_str = st.session_state.end_time_val.strftime("%H:%M")
                
                route, closed, skipped = solve_route_with_priorities(
                    park_keuze, must_haves, should_haves, s_str, e_str, 
                    start_location=st.session_state.current_loc,
                    lunch_config=lunch_config
                )
                st.session_state.last_route = route
                st.session_state.last_closed = closed

    if st.session_state.last_route:
        route = st.session_state.last_route
        if st.session_state.last_closed and not is_park_closed: 
            st.error(f"⛔ Gesloten: {', '.join(st.session_state.last_closed)}")

        rides_only = [r for r in route if r['type'] != 'LUNCH']
        ai_wait = sum(s['wait_min'] for s in rides_only)
        m1, m2, m3 = st.columns(3)
        m1.metric("Rides", len(rides_only))
        m2.metric("Wachttijd", f"{ai_wait} min")
        m3.metric("Volgende", route[0]['ride'] if route else "Klaar")

        st.subheader("👇 Jouw Planning")
        for i, step in enumerate(route):
            is_next = (i == 0)
            label = f"**{step['start_walk']}** | Ga naar {step['ride']}"
            if is_next: label = "👉 " + label

            with st.expander(label, expanded=is_next):
                c1, c2, c3 = st.columns([2,2,1])
                if step['type'] == "LUNCH":
                    c1.write(f"🚶 Loop: {step['walk_min']} min")
                    c2.info(f"Pauze: {step['note']}")
                    if c3.button("✅ Gegeten!", key=f"lunch_{i}"):
                        st.session_state.lunch_done = True
                        st.session_state.current_loc = step['ride'].replace("🍽️ Lunch: ", "")
                        st.session_state.last_route = None
                        st.session_state.start_time_val = datetime.datetime.now().time()
                        st.rerun()
                else:
                    c1.write(f"🚶 Loop: {step['walk_min']} min")
                    c1.write(f"⏳ Wacht: {step['wait_min']} min")
                    info = step['note']
                    if step['type'] == "MUST": info += " | ⭐ Prio"
                    c2.info(info)
                    c3.button("✅ Gedaan!", key=f"done_{step['ride']}_{i}", on_click=mark_done, args=(step['ride'],))
    elif st.session_state.last_route == []:
        st.success("🎉 Alles gedaan!")

# TAB 2: BESTE TIJDEN
# TAB 2: BESTE TIJDEN
with tab_best:
    st.subheader("🔍 Zoek het beste moment (Vandaag)")
    target = active_selection
    if target:
        s_range = st.slider("Zoekvenster:", 10, 19, (12, 16))
        now = datetime.datetime.now()
        cols = st.columns(3)
        
        for i, ride in enumerate(target):
            best_h, min_w = -1, 999
            
            # FIX: We voegen +1 toe aan s_range[1]
            # Hierdoor werkt range(16, 17) correct voor het uur 16:00
            start_h = s_range[0]
            end_h = s_range[1] + 1 

            for h in range(start_h, end_h):
                t = now.replace(hour=h, minute=0)
                w = get_wait_time_prediction(park_keuze, ride, t, live_data)
                
                # Fallback check
                if isinstance(w, dict): w = 15
                
                # Update beste tijd als deze wachttijd lager is
                if w < min_w: 
                    min_w, best_h = w, h
            
            # Check of er een geldige tijd is gevonden (voorkomt -1 weergave)
            if best_h != -1:
                border_c = "#39FF14" if min_w < 15 else ("#FFC107" if min_w < 45 else "#FF4B4B")
                html = f"""
                <div class="advice-card" style="border-left: 5px solid {border_c};">
                    <div class="advice-title">{ride}</div>
                    <div class="advice-time">Om {best_h}:00</div>
                    <div class="advice-wait">⏳ Verwacht: {min_w} min</div>
                </div>
                """
                with cols[i % 3]: st.markdown(html, unsafe_allow_html=True)
            else:
                # Fallback als er iets misgaat met de range
                st.warning(f"Geen data voor {ride}")
                
    else: st.info("Kies eerst attracties.")
# TAB 3: TOEKOMST
with tab_future:
    st.subheader("🔮 Precisie Simulatie")
    c1, c2 = st.columns(2)
    fut_date = c1.date_input("Datum", datetime.date.today() + datetime.timedelta(days=1))
    
    with st.expander("🌦️ Weer & Instellingen", expanded=False):
        wc1, wc2, wc3 = st.columns(3)
        sim_temp = wc1.slider("Temp (°C)", -5, 35, 20)
        sim_rain_prob = wc2.slider("Neerslag (%)", 0, 100, 0, step=10)
        rain_opts = {"Geen": 0.0, "Motregen": 0.5, "Regen": 2.0, "Stortbui": 8.0}
        sim_rain_mm = rain_opts[wc3.selectbox("Type", list(rain_opts.keys()))]
        sim_cond = "Cloudy"
        if sim_rain_prob >= 40: sim_cond = "Rain: Light"
        if sim_rain_prob >= 70 and sim_rain_mm >= 2.0: sim_cond = "Rain: Heavy"
        if sim_rain_prob <= 20 and sim_rain_mm == 0: sim_cond = "Clear Sky"
    
    target_future = active_selection if active_selection else rides_all[:5]
    
    if st.button("🔮 Voorspel Dagverloop", type="primary"):
        chart_data = []
        
        # 1. DATA GENEREREN
        with st.spinner("Modellen draaien simulatie..."):
            for ride in target_future:
                for h in range(10, 19):
                    sim_time = datetime.datetime.combine(fut_date, datetime.time(h, 0))
                    w = get_wait_time_prediction(park_keuze, ride, sim_time, weather_override={"temp_c": sim_temp, "precip_mm": sim_rain_mm, "condition": sim_cond})
                    # Fallback als return een dict is
                    val = w if isinstance(w, int) else 15
                    chart_data.append({"Uur": f"{h}:00", "UurInt": h, "Attractie": ride, "Wachttijd": val})

        # Dataframe maken voor analyse
        df_chart = pd.DataFrame(chart_data)

        # 2. GRAFIEK
        st.markdown("### 📈 Wachttijd Verloop")
        fig = px.line(df_chart, x="Uur", y="Wachttijd", color="Attractie", markers=True)
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", 
            paper_bgcolor="rgba(0,0,0,0)", 
            font=dict(color="white"), 
            legend_font_color="white",
            yaxis_title="Minuten Wacht",
            xaxis_title="Tijdstip"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # 3. BESTE TIJDEN (CARDS)
        st.markdown("### 🏆 Beste Momenten (Simulatie)")
        cols_best = st.columns(3)
        
        # Voor elke attractie, zoek de rij met minste wachttijd
        for i, ride in enumerate(target_future):
            ride_data = df_chart[df_chart["Attractie"] == ride]
            if not ride_data.empty:
                best_row = ride_data.loc[ride_data["Wachttijd"].idxmin()]
                min_w = best_row["Wachttijd"]
                best_h = best_row["Uur"]
                
                border_c = "#39FF14" if min_w < 15 else ("#FFC107" if min_w < 45 else "#FF4B4B")
                
                html = f"""
                <div class="advice-card" style="border-left: 5px solid {border_c};">
                    <div class="advice-title">{ride}</div>
                    <div class="advice-time">{best_h}</div>
                    <div class="advice-wait">⏳ Verwacht: {min_w} min</div>
                </div>
                """
                with cols_best[i % 3]: st.markdown(html, unsafe_allow_html=True)

        st.divider()

        # 4. DAG GEMIDDELDES (METRICS)
        st.markdown("### 📊 Dag Rapport (Gemiddelden)")
        
        # Bereken gemiddelde per attractie
        avg_data = df_chart.groupby("Attractie")["Wachttijd"].mean().sort_values().reset_index()
        
        # Weergave in rijen van 4 metrics
        col_it = st.columns(4)
        for idx, row in avg_data.iterrows():
            avg_w = round(row['Wachttijd'])
            ride = row['Attractie']
            
            # Kleur code voor de tekst
            color = "#64B5F6" # Blauw (standaard)
            if avg_w < 15: color = "#39FF14" # Groen
            elif avg_w > 45: color = "#FF4B4B" # Rood
            
            html_metric = f"""
            <div class="metric-box">
                <div class="metric-val" style="color: {color};">{avg_w} <span style="font-size:0.5em;">min</span></div>
                <div class="metric-lbl">{ride}</div>
            </div>
            """
            with col_it[idx % 4]: st.markdown(html_metric, unsafe_allow_html=True)

# TAB 4: VOLTOOID
with tab_done:
    if st.session_state.completed:
        st.success(f"Al {len(st.session_state.completed)} gedaan!")
        cols = st.columns(3)
        for i, r in enumerate(st.session_state.completed):
            cols[i % 3].success(f"✅ {r}")
        if st.button("🗑️ Reset Alles"):
            for k in st.session_state.keys(): del st.session_state[k]
            st.rerun()
    else:

        st.info("Nog niks gedaan.")
