import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
import numpy as np
import importlib
import pytz 

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
    
    /* Cards styling */
    .advice-card {
        background-color: #1F2937; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #FFC107;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: transform 0.2s;
    }
    .advice-card:hover { transform: translateY(-2px); }
    .advice-title { font-weight: bold; font-size: 1.1em; color: white; margin-bottom: 5px; }
    .advice-time { font-size: 1.4em; font-weight: bold; color: #FFC107; }
    .advice-wait { font-size: 0.9em; color: #B0BEC5; }
    
    /* Metric box */
    .metric-box {
        background-color: #262730; border-radius: 8px; padding: 10px; text-align: center; border: 1px solid #444;
    }
    .metric-val { font-size: 1.5em; font-weight: bold; color: #64B5F6; }
    .metric-lbl { font-size: 0.8em; color: #AAA; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES VOOR UITLEG EN STRATEGIE ---

def generate_strategy_explanation(route, park_name):
    """Genereert een logische verklaring voor de gekozen route."""
    if not route: return None, None
    
    first_ride = route[0]['ride']
    rides_only = [r for r in route if r['type'] != 'LUNCH']
    total_walk = sum(r['walk_min'] for r in rides_only)
    avg_walk = total_walk / len(rides_only) if rides_only else 0
    
    # Lijst met 'Ochtend-Killers'
    headliners = {
        "EFTELING": ["Baron 1898", "Symbolica", "De Vliegende Hollander", "Joris en de Draak"],
        "PHANTASIALAND": ["Taron", "F.L.Y.", "Black Mamba", "Maus au Chocolat"],
        "WALIBI_BELGIUM": ["Kondaa", "Pulsar", "Psyké Underground"]
    }
    
    # SCENARIO 1: De Knalstart
    if park_name in headliners and any(h in first_ride for h in headliners[park_name]):
        return "🚀 De 'Knalstart' Strategie", f"We sturen je direct naar **{first_ride}**. Dit is de populairste attractie; door deze nu te pakken, bespaar je later op de dag waarschijnlijk 30+ minuten wachten."

    # SCENARIO 2: De Efficiënte Loper
    if avg_walk < 4: 
        return "👟 De 'Efficiënte' Strategie", "Deze route bundelt attracties die dicht bij elkaar liggen. Je looptijd is minimaal, waardoor je meer tijd overhoudt voor ritjes en terrasjes."

    # SCENARIO 3: De 'Opbouw'
    if route[0]['wait_min'] <= 10:
        return "📈 De 'Opbouw' Strategie", f"We beginnen rustig bij **{first_ride}** om direct een succesje te boeken met korte wachttijd. De drukkere attracties plannen we later."

    # DEFAULT
    return "⚖️ De 'Balans' Strategie", "Deze volgorde is berekend om een optimale mix te vinden tussen jouw Must-Haves prioriteit geven en kriskras door het park lopen voorkomen."

def get_step_reason(step, prev_step_loc, park_name, live_data):
    """
    Bepaalt de reden en berekent 'Opportunity Cost' (Winst t.o.v. later gaan).
    """
    ride = step['ride']
    wait_now = step['wait_min']
    walk = step['walk_min']
    
    # 1. Is het een Lunch?
    if step['type'] == 'LUNCH':
        return "🍽️ Tijd om even op te laden."

    # 2. TOEKOMST ANALYSE
    try:
        tz = pytz.timezone('Europe/Brussels')
        now = datetime.datetime.now(tz)
        today = now.date()
        h, m = map(int, step['arrival_time'].split(':'))
        arrival_dt = tz.localize(datetime.datetime.combine(today, datetime.time(h, m)))
        
        # We kijken 2 uur in de toekomst
        future_check_time = arrival_dt + datetime.timedelta(hours=2)
        
        # Voorspel wachttijd in de toekomst
        wait_later = get_wait_time_prediction(park_name, ride, future_check_time, live_data_snapshot=None)
        if isinstance(wait_later, dict): wait_later = 15
        
        time_saved = wait_later - wait_now
        
    except:
        time_saved = 0

    # --- DE STRATEGIE REGELS ---

    # REGEL A: De "Meesterzet"
    if time_saved >= 15:
        return f"📉 **Slimme zet:** Straks loopt de rij hier op naar ca. {wait_later} min. **Je bespaart {time_saved} min** door nu te gaan."

    # REGEL B: De "Vroege Vogel"
    headliners = ["Baron 1898", "Symbolica", "Joris en de Draak", "Taron", "F.L.Y.", "Black Mamba", "Kondaa"]
    if any(h in ride for h in headliners) and wait_now < 15:
        return f"⚡ **Kans:** Topattractie met slechts {wait_now} min wachtrij. Pakken nu het kan!"

    # REGEL C: De "Buurman"
    if walk <= 3 and prev_step_loc != "Ingang":
        extra_msg = ""
        if time_saved > 5: extra_msg = f" (En je bespaart {time_saved} min t.o.v. vanmiddag)"
        return f"📍 **Dichtbij:** Ligt praktisch naast je vorige locatie.{extra_msg}"

    # REGEL D: De "Snelle Hap"
    if step['type'] == "SHOULD" and wait_now <= 5:
        return "👌 **Opvulling:** Wachttijd is minimaal, dus prima om 'mee te pakken' op weg naar de volgende."

    # REGEL E: Consistentie
    if time_saved >= 5:
        return f"✅ **Goede Timing:** Het is nu {time_saved} min rustiger dan gemiddeld vanmiddag."

    return "⚖️ **Route Optimalisatie:** Past nu het beste in je reisschema."
    

# --- 1. STATE INITIALISATIE ---
defaults = {
    'completed': [],
    'current_loc': "Ingang",
    'live_data': {},
    'lunch_done': False,
    'last_route': None,
    'last_closed': [],
    'mc': [], 'sc': [], 
    'md': [], 'sd': [], 
    'mo': [], 'so': [] 
}

for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# Tijd State (Timezone Aware)
if 'start_time_val' not in st.session_state:
    tz = pytz.timezone('Europe/Brussels')
    now = datetime.datetime.now(tz)
    st.session_state.start_time_val = datetime.time(10, 0) if now.hour < 10 else now.time()

if 'end_time_val' not in st.session_state:
    st.session_state.end_time_val = datetime.time(18, 0)

# --- CALLBACKS ---
def update_start_time(): st.session_state.start_time_val = st.session_state.widget_start_time
def update_end_time(): st.session_state.end_time_val = st.session_state.widget_end_time

def mark_done(ride_name):
    if ride_name not in st.session_state.completed:
        st.session_state.completed.append(ride_name)
    st.session_state.current_loc = ride_name
    st.session_state.last_route = None
    
    # Update tijd naar NU
    tz = pytz.timezone('Europe/Brussels')
    st.session_state.start_time_val = datetime.datetime.now(tz).time()

st.title("🎢 QueueQuest Ultimate")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Instellingen")
park_keuze = st.sidebar.selectbox("Park:", ("EFTELING", "PHANTASIALAND", "WALIBI_BELGIUM"))

all_meta = {k: v for k, v in ATTRACTION_METADATA.items() if v['park'] == park_keuze}
rides_all = sorted([r for r, m in all_meta.items() if m.get('type') not in ['Restaurant', 'Snack'] and "Single-rider" not in r])
restaurants = sorted([r for r, m in all_meta.items() if m.get('type') in ['Restaurant', 'Snack']])

st.sidebar.subheader("📍 Locatie")
loc_options = ["Ingang"] + rides_all + restaurants
if st.session_state.current_loc not in loc_options: st.session_state.current_loc = "Ingang"
st.sidebar.selectbox("Je bent nu bij:", loc_options, key="current_loc")

# --- SELECTIE ---
st.sidebar.subheader("🎯 Wensenlijst")
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

# Live data knop
if st.sidebar.button("🔄 Ververs Live Data"):
    with st.spinner("Verbinden met park servers..."):
        st.session_state.live_data = fetch_live_data(park_keuze)
live_data = st.session_state.get('live_data', {})

active_selection = must_haves + should_haves
is_park_closed = len(live_data) > 0 and len([r for r in live_data.values() if r['is_open']]) < 3
if not is_park_closed and live_data:
    closed_now = [r for r in active_selection if r in live_data and not live_data[r]['is_open']]
    if closed_now: st.sidebar.error(f"⛔ Nu Gesloten: {', '.join(closed_now)}")
elif is_park_closed: st.sidebar.info("ℹ️ Park gesloten (Forecast Modus)")

# --- WAIT OR GO ADVISEUR (SIDEBAR) ---
# DIT STUK MOET STRAK LINKS STAAN
if not is_park_closed and active_selection:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 Wait or Go?")
    
    # We kijken alleen naar je Must-Haves
    targets = st.session_state.mc + st.session_state.md + st.session_state.mo
    
    if not targets:
        st.sidebar.caption("Selecteer 'Must-Haves' voor advies.")
    else:
        tz = pytz.timezone('Europe/Brussels')
        now_advice = datetime.datetime.now(tz)
        future_advice = now_advice + datetime.timedelta(minutes=45) 
        
        advice_count = 0
        
        for ride in targets:
            if ride not in live_data or not live_data[ride]['is_open']:
                continue
                
            current_w = live_data[ride]['wait_time']
            
            # Forecast voor toekomst
            future_w = get_wait_time_prediction(park_keuze, ride, future_advice, live_data_snapshot=None)
            if isinstance(future_w, dict): future_w = 15
            
            diff = future_w - current_w
            
            # Advies Logica
            if diff >= 10:
                st.sidebar.success(f"🏃 **REN naar {ride}!**\n\nNu: {current_w}m ➝ Straks: {future_w}m\n*(Bespaar {diff} min)*")
                advice_count += 1
            elif diff <= -10:
                st.sidebar.warning(f"☕ **Wacht met {ride}**\n\nNu: {current_w}m ➝ Straks: {future_w}m\n*(Het zakt {abs(diff)} min)*")
                advice_count += 1
        
        if advice_count == 0:
            st.sidebar.info("Geen sterke stijgers of dalers voorspeld.")


# --- TABS ---
tab_copilot, tab_radar, tab_best, tab_future, tab_done = st.tabs(["📍 Live Route", "⚡ Radar", "📊 Beste Tijden", "📅 Toekomst", "✅ Voltooid"])

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

        # --- AI STRATEGIE UITLEG ---
        strat_title, strat_msg = generate_strategy_explanation(route, park_keuze)
        if strat_title:
            st.info(f"**{strat_title}**\n\n{strat_msg}", icon="🧠")

        rides_only = [r for r in route if r['type'] != 'LUNCH']
        ai_wait = sum(s['wait_min'] for s in rides_only)
        m1, m2, m3 = st.columns(3)
        m1.metric("Rides", len(rides_only))
        m2.metric("Wachttijd", f"{ai_wait} min")
        m3.metric("Volgende", route[0]['ride'] if route else "Klaar")

        st.subheader("👇 Jouw Planning")
        
        prev_loc = st.session_state.current_loc 

        for i, step in enumerate(route):
            is_next = (i == 0)
            
            icon = "🎢"
            if step['type'] == "LUNCH": icon = "🍔"
            elif "Coaster" in ATTRACTION_METADATA.get(step['ride'], {}).get('type', ''): icon = "🎢"
            elif "DarkRide" in ATTRACTION_METADATA.get(step['ride'], {}).get('type', ''): icon = "👻"
            
            label = f"**{step['start_walk']}** | {icon} Ga naar {step['ride']}"
            if is_next: label = "👉 " + label

            with st.expander(label, expanded=is_next):
                c1, c2, c3 = st.columns([2,2,1])
                
                # --- SLIMME REDEN AANROEPEN ---
                reason_msg = get_step_reason(step, prev_loc, park_keuze, live_data)
                
                if step['type'] == "LUNCH":
                    c1.write(f"🚶 Loop: {step['walk_min']} min")
                    c2.info(f"{reason_msg}\n\n*Duur: {step['note']}*")
                    if c3.button("✅ Gegeten!", key=f"lunch_{i}"):
                        st.session_state.lunch_done = True
                        st.session_state.current_loc = step['ride'].replace("🍽️ Lunch: ", "")
                        st.session_state.last_route = None
                        tz = pytz.timezone('Europe/Brussels')
                        st.session_state.start_time_val = datetime.datetime.now(tz).time()
                        st.rerun()
                else:
                    c1.write(f"🚶 Loop: {step['walk_min']} min")
                    c1.write(f"⏳ Wacht: {step['wait_min']} min")
                    
                    source_label = "Live Data" if "Live" in step['note'] else "Forecast"
                    prio_label = " | ⭐ Must-Do" if step['type'] == "MUST" else ""
                    
                    c2.info(f"{reason_msg}\n\n*({source_label}{prio_label})*")
                    
                    c3.button("✅ Gedaan!", key=f"done_{step['ride']}_{i}", on_click=mark_done, args=(step['ride'],))
            
            prev_loc = step['ride']

    elif st.session_state.last_route == []:
        st.success("🎉 Alles gedaan!")

# TAB 2: MARKET ANALYSIS (RADAR)
with tab_radar:
    st.subheader("📉 Markt Analyse: Waar zit de winst?")
    
    # --- DE BENCHMARK SCHAKELAAR ---
    c_mode, c_info = st.columns([1, 2])
    benchmark_mode = c_mode.radio(
        "Vergelijk met:", 
        ["🤖 AI Verwachting (Vandaag)", "📊 Jaargemiddelde (Statisch)"],
        help="AI kijkt naar de voorspelling voor vandaag (weer/dag). Jaargemiddelde is een vast getal."
    )
    
    if benchmark_mode.startswith("🤖"):
        c_info.info("💡 Je vergelijkt nu met wat het model **voor vandaag** had voorspeld. Als het groen is, is het dus rustiger dan verwacht voor deze specifieke dag.")
    else:
        c_info.info("💡 Je vergelijkt nu met het **gemiddelde over het hele jaar**. Op rustige dagen zal alles groen lijken.")

    st.divider()

    if not live_data:
        st.warning("Geen live data beschikbaar. Druk op '🔄 Ververs Live Data' in de sidebar.")
    else:
        # 'Normale' wachttijden
        historical_averages = {
            "Baron 1898": 40, "Python": 25, "Vliegende Hollander": 40,
            "Joris en de Draak": 35, "Droomvlucht": 35, "Symbolica": 35,
            "Vogel Rok": 15, "Fata Morgana": 15, "Piraña": 20,
            "Max & Moritz": 20, "Sprookjesbos": 5, "Carnaval Festival": 20,
            "Danse Macabre": 60,
            "Taron": 65, "Black Mamba": 30, "F.L.Y.": 75, "Chiapas": 35,
            "Maus au Chocolat": 30, "Winja's Fear": 25, "Winja's Force": 25,
            "Crazy Bats": 10, "Colorado Adventure": 20, "Mystery Castle": 15,
            "River Quest": 45, "Talocan": 15,
            "Kondaa": 55, "Pulsar": 25, "Tiki-Waka": 35, "Werewolf": 30,
            "Psyké Underground": 25, "Cobra": 25, "Vampire": 30
        }

        radar_data = []
        tz = pytz.timezone('Europe/Brussels')
        now_radar = datetime.datetime.now(tz)

        for ride_name, data in live_data.items():
            if not data['is_open']: continue

            curr_wait = data['wait_time']
            
            if "AI" in benchmark_mode:
                predicted = get_wait_time_prediction(park_keuze, ride_name, now_radar, live_data_snapshot=None)
                if isinstance(predicted, dict): predicted = 15
                norm_wait = predicted
            else:
                norm_wait = historical_averages.get(ride_name, curr_wait) 
            
            diff = norm_wait - curr_wait 
            
            status = "Fair Value"
            if diff >= 15: status = "🔥 STRONG BUY"
            elif diff >= 5: status = "🟢 Buy"
            elif diff <= -15: status = "⛔ SELL / AVOID"
            elif diff <= -5: status = "🔴 Overpriced"
            
            radar_data.append({
                "Attractie": ride_name,
                "Nu": curr_wait,
                "Benchmark": norm_wait, 
                "Winst": diff,
                "Status": status
            })
        
        df_radar = pd.DataFrame(radar_data)
        
        if not df_radar.empty:
            df_radar = df_radar.sort_values(by="Winst", ascending=False)
            top_picks = df_radar.head(3)
            col_label = "AI Verwacht" if "AI" in benchmark_mode else "Jaar Gem."
            
            st.markdown(f"### 🏆 Top 3 'Outperformers' (vs {col_label})")
            cols = st.columns(3)
            for i, (index, row) in enumerate(top_picks.iterrows()):
                label_color = "normal"
                if row['Winst'] > 0: label_color = "normal"
                elif row['Winst'] < 0: label_color = "inverse"

                cols[i].metric(
                    label=row['Attractie'],
                    value=f"{row['Nu']} min",
                    delta=f"{row['Winst']} min (Sneller)",
                    delta_color=label_color
                )

            st.divider()

            st.markdown("### 📋 Volledig Marktoverzicht")
            
            def color_status(val):
                color = 'white'; weight = 'normal'
                if "STRONG BUY" in val: color = '#39FF14'; weight = 'bold'
                elif "Buy" in val: color = '#66BB6A'; weight = 'bold'
                elif "SELL" in val: color = '#FF4B4B'; weight = 'bold'
                elif "Overpriced" in val: color = '#FF8A80'
                return f'color: {color}; font-weight: {weight}'

            st.dataframe(
                df_radar.style.map(color_status, subset=['Status'])
                .format({"Nu": "{} min", "Benchmark": "{} min", "Winst": "{:+d} min"}),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Attractie": st.column_config.TextColumn("Attractie", width="medium"),
                    "Nu": st.column_config.NumberColumn("Huidig", format="%d min"),
                    "Benchmark": st.column_config.NumberColumn(col_label, format="%d min"),
                    "Winst": st.column_config.NumberColumn("Voordeel", format="%+d min"),
                    "Status": st.column_config.TextColumn("Advies", width="small")
                }
            )
        else:
            st.info("Geen open attracties gevonden.")

# TAB 3: BESTE TIJDEN
with tab_best:
    st.subheader("🔍 Zoek het beste moment (Vandaag)")
    target = active_selection
    if target:
        s_range = st.slider("Zoekvenster:", 10, 19, (12, 16))
        tz = pytz.timezone('Europe/Brussels')
        now = datetime.datetime.now(tz)
        cols = st.columns(3)
        
        for i, ride in enumerate(target):
            best_h, min_w = -1, 999
            start_h, end_h = s_range[0], s_range[1] + 1 

            for h in range(start_h, end_h):
                t = now.replace(hour=h, minute=0)
                w = get_wait_time_prediction(park_keuze, ride, t, live_data)
                if isinstance(w, dict): w = 15
                if w < min_w: min_w, best_h = w, h
            
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
    else: st.info("Kies eerst attracties.")

# TAB 4: TOEKOMST
with tab_future:
    st.subheader("🔮 Precisie Simulatie")
    c1, c2 = st.columns(2)
    fut_date = c1.date_input("Datum", datetime.date.today() + datetime.timedelta(days=1))
    
    with st.expander("🌦️ Weer & Instellingen", expanded=False):
        wc1, wc2, wc3 = st.columns(3)
        sim_temp = wc1.slider("Temp (°C)", -5, 35, 20)
        sim_rain_prob = wc2.slider("Neerslag (%)", 0, 100, 0, step=10)
        sim_rain_mm = 0.0 if sim_rain_prob < 20 else 2.0
        
    target_future = active_selection if active_selection else rides_all[:5]
    
    if st.button("🔮 Voorspel Dagverloop", type="primary"):
        chart_data = []
        with st.spinner("Modellen draaien simulatie..."):
            for ride in target_future:
                for h in range(10, 19):
                    sim_time = datetime.datetime.combine(fut_date, datetime.time(h, 0))
                    w = get_wait_time_prediction(park_keuze, ride, sim_time, weather_override={"temp_c": sim_temp, "precip_mm": sim_rain_mm})
                    val = w if isinstance(w, int) else 15
                    chart_data.append({"Uur": f"{h}:00", "Attractie": ride, "Wachttijd": val})

        df_chart = pd.DataFrame(chart_data)
        st.markdown("### 📈 Wachttijd Verloop")
        fig = px.line(df_chart, x="Uur", y="Wachttijd", color="Attractie", markers=True)
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
        st.plotly_chart(fig, use_container_width=True)

# TAB 5: VOLTOOID
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