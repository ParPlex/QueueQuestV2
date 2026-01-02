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

# Importeer BEIDE solvers
from route_solver import solve_route_with_priorities, solve_max_score_route, fetch_live_data, get_wait_time_prediction
from queuequest_meta import ATTRACTION_METADATA
from holiday_utils import is_crowd_risk_day

# Probeer weather_utils te laden (zodat het script niet crasht als het bestand mist)
try:
    from weather_utils import get_automated_weather
except ImportError:
    # Fallback functie als het bestand er niet is
    def get_automated_weather(park, date):
        return {"temp_c": 15, "precip_mm": 0.0, "rain_prob": 10, "source": "⚠️ Fallback"}

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

# --- FUNCTIES VOOR UITLEG EN STRATEGIE (GEOPTIMALISEERD MET CACHE) ---

@st.cache_data(show_spinner=False)
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
    
    # Check voor Score Modus (heeft geen wait_min direct beschikbaar in alle gevallen)
    wait_now = step.get('wait_min', 0)
    walk = step.get('walk_min', 0)
    
    # 1. Is het een Lunch?
    if step['type'] == 'LUNCH':
        return "🍽️ Tijd om even op te laden."
    
    # 2. Is het een Score Run?
    if step['type'] == 'SCORE':
        return "💎 **Punten Pakker:** Deze attractie levert nu de meeste waarde (plezier/tijd) op."

    # 3. TOEKOMST ANALYSE
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

# --- 2. INTELLIGENTE TIJD INITIALISATIE ---
if 'start_time_val' not in st.session_state:
    tz = pytz.timezone('Europe/Brussels')
    now = datetime.datetime.now(tz)
    
    # Check: Is het tussen 10:00 en 18:00?
    if 10 <= now.hour < 18:
        # Ja: Pak huidige tijd
        st.session_state.start_time_val = now.time().replace(second=0, microsecond=0)
    else:
        # Nee: Pak 10:00
        st.session_state.start_time_val = datetime.time(10, 0)

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

# --- NIEUW: HET LOOP-PROFIEL (SLIDER) ---
st.sidebar.subheader("🏃 Wandeltempo")
pace_select = st.sidebar.select_slider(
    "Hoe snel loop je?",
    options=["Relaxed 🐢", "Gemiddeld 🚶", "Haastig 🐇"],
    value="Gemiddeld 🚶"
)
# Vertaal selectie naar factor (1.0 = normaal, >1 = trager, <1 = sneller)
pace_map = {"Relaxed 🐢": 1.4, "Gemiddeld 🚶": 1.0, "Haastig 🐇": 0.7}
pace_factor = pace_map[pace_select]

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

# --- AGGREGATIE (DE FIX) ---
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

# Live data knop (AANGEPAST VOOR CACHING)
if st.sidebar.button("🔄 Ververs Live Data"):
    # HIER LEGEN WE DE CACHE OM EEN ECHTE REFRESH TE FORCEREN
    st.cache_data.clear()
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


# --- TABS (HERINGEDEELD) ---
tab_copilot, tab_radar, tab_best, tab_future, tab_perfect, tab_done = st.tabs([
    "📍 Live Route", 
    "⚡ Radar", 
    "📊 Beste Tijden", 
    "📅 Toekomst", 
    "🏆 Perfecte Route", 
    "✅ Voltooid"
])

# TAB 1: CO-PILOOT
with tab_copilot:
    c1, c2 = st.columns(2)
    c1.time_input("Starttijd", value=st.session_state.start_time_val, key="widget_start_time", on_change=update_start_time)
    c2.time_input("Eindtijd", value=st.session_state.end_time_val, key="widget_end_time", on_change=update_end_time)
    
    if st.button("🚀 Bereken Route", type="primary", use_container_width=True):
        if not active_selection and not lunch_config:
            st.warning("Kies eerst attracties in de zijbalk.")
        else:
            with st.spinner("AI berekent route..."):
                s_str = st.session_state.start_time_val.strftime("%H:%M")
                e_str = st.session_state.end_time_val.strftime("%H:%M")
                
                route, closed, skipped = solve_route_with_priorities(
                    park_name=park_keuze,
                    must_haves=must_haves,
                    should_haves=should_haves,
                    start_str=s_str,
                    end_str=e_str, 
                    start_location=st.session_state.current_loc,
                    lunch_config=lunch_config,
                    pace_factor=pace_factor 
                )
                st.session_state.last_route = route
                st.session_state.last_closed = closed

    if st.session_state.last_route:
        route = st.session_state.last_route
        if st.session_state.last_closed and not is_park_closed: 
            st.error(f"⛔ Gesloten: {', '.join(st.session_state.last_closed)}")

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
        if st.session_state.last_closed:
            st.error("⛔ Geen route mogelijk: Al je gekozen attracties zijn gesloten!")
            st.write("De volgende attracties zijn dicht:")
            for c in st.session_state.last_closed:
                st.write(f"- 🔴 {c}")
        elif not active_selection:
            st.warning("👈 Selecteer eerst attracties in de zijbalk.")
        else:
            st.success("🎉 Alles gedaan! Je hebt je hele lijst afgewerkt.")

# TAB 2: MARKET ANALYSIS (MARKET WATCH)
with tab_radar:
    st.subheader("📉 Market Watch: Kansen & Valkuilen")
    
    # --- 1. CONFIGURATIE & FILTERS ---
    c_filters, c_info = st.columns([2, 2])
    
    with c_filters:
        benchmark_mode = st.radio(
            "Vergelijk met:", 
            ["🤖 AI Verwachting (Vandaag)", "📊 Jaargemiddelde"],
            horizontal=True,
            label_visibility="collapsed"
        )
        score_filter = st.select_slider(
            "Filter op Kwaliteit:",
            options=["Alles", "Vanaf 6 (Goed)", "8+ (Alleen Toppers)"],
            value="Alles"
        )

    if benchmark_mode.startswith("🤖"):
        c_info.info("💡 **AI Modus:** Vergelijkt live drukte met de voorspelling voor *vandaag*.")
    else:
        c_info.info("💡 **Historisch:** Vergelijkt live drukte met het *gemiddelde* van het jaar.")

    st.divider()

    if not live_data:
        st.warning("Geen live data beschikbaar. Druk op '🔄 Ververs Live Data' in de sidebar.")
    else:
        historical_averages = {
            "Baron 1898": 40, "Python": 25, "Vliegende Hollander": 35,
            "Joris en de Draak": 35, "Droomvlucht": 35, "Symbolica": 35,
            "Vogel Rok": 15, "Fata Morgana": 15, "Piraña": 20,
            "Max & Moritz": 20, "Carnaval Festival": 20, "Danse Macabre": 60,
            "Taron": 60, "Black Mamba": 30, "F.L.Y.": 70, "Chiapas": 30,
            "Maus au Chocolat": 30, "Winja's Fear": 25, "Winja's Force": 25,
            "Kondaa": 50, "Pulsar": 25, "Tiki-Waka": 30, "Psyké Underground": 25
        }

        market_data = []
        tz = pytz.timezone('Europe/Brussels')
        now_radar = datetime.datetime.now(tz)

        for ride_name, data in live_data.items():
            if not data['is_open']: continue

            curr_wait = data['wait_time']
            meta = ATTRACTION_METADATA.get(ride_name, {})
            score = meta.get('score', 5)
            
            if score_filter == "Vanaf 6 (Goed)" and score < 6: continue
            if score_filter == "8+ (Alleen Toppers)" and score < 8: continue

            if "AI" in benchmark_mode:
                predicted = get_wait_time_prediction(park_keuze, ride_name, now_radar, live_data_snapshot=None)
                if isinstance(predicted, dict): predicted = 20
                norm_wait = predicted
            else:
                norm_wait = historical_averages.get(ride_name, curr_wait) 
            
            diff = norm_wait - curr_wait 
            
            if norm_wait > 5 or curr_wait > 5:
                market_data.append({
                    "Attractie": ride_name,
                    "Nu": curr_wait,
                    "Normaal": norm_wait, 
                    "Winst": diff,
                    "Score": score
                })
        
        df_market = pd.DataFrame(market_data)

        if not df_market.empty:
            st.markdown("### 🎯 Opportunity Matrix")
            fig = px.scatter(
                df_market,
                x="Normaal",
                y="Winst",
                color="Winst",
                size="Score", 
                text="Attractie",
                color_continuous_scale="RdYlGn", 
                range_color=[-20, 20],
                labels={"Normaal": "Normale Drukte", "Winst": "Minuten Sneller"},
                height=450
            )
            
            fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Gemiddeld")
            fig.update_traces(textposition='top center', marker=dict(line=dict(width=1, color='DarkSlateGrey')))
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", 
                paper_bgcolor="rgba(0,0,0,0)", 
                font=dict(color="white"),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True) # FIX: width="stretch" indien nodig, maar use_container_width is veilige fallback voor oudere versies
            
            st.caption(f"Leeswijzer: Rechtsboven zijn de toppers die nu rustig zijn. (Filter actief: {score_filter})")

            st.divider()

            c_win, c_loss = st.columns(2)
            
            with c_win:
                st.subheader("🟢 Nu Doen (Sneller)")
                winners = df_market[df_market['Winst'] >= 5].sort_values("Winst", ascending=False)
                if winners.empty: st.caption("Geen koopjes gevonden.")
                else:
                    for _, row in winners.iterrows():
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(30, 200, 80, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 8px; border-left: 4px solid #4CAF50;">
                                <div style="font-weight: bold; font-size: 1.1em;">{row['Attractie']} <span style="font-size:0.8em; color:#AAA;">(⭐{row['Score']})</span></div>
                                <div style="display: flex; justify-content: space-between;">
                                    <span>Nu: <b style="color: #4CAF50;">{row['Nu']} min</b></span>
                                    <span style="color: #AAA;">(Normaal: {row['Normaal']})</span>
                                </div>
                                <div style="font-size: 0.9em; color: #4CAF50;">▼ {row['Winst']} min winst</div>
                            </div>
                            """, unsafe_allow_html=True
                        )

            with c_loss:
                st.subheader("🔴 Nu Vermijden (Trager)")
                losers = df_market[df_market['Winst'] <= -5].sort_values("Winst", ascending=True)
                if losers.empty: st.caption("Geen grote files.")
                else:
                    for _, row in losers.iterrows():
                        extra_time = abs(row['Winst'])
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(255, 80, 80, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 8px; border-left: 4px solid #FF5252;">
                                <div style="font-weight: bold; font-size: 1.1em;">{row['Attractie']} <span style="font-size:0.8em; color:#AAA;">(⭐{row['Score']})</span></div>
                                <div style="display: flex; justify-content: space-between;">
                                    <span>Nu: <b style="color: #FF5252;">{row['Nu']} min</b></span>
                                    <span style="color: #AAA;">(Normaal: {row['Normaal']})</span>
                                </div>
                                <div style="font-size: 0.9em; color: #FF5252;">▲ {extra_time} min trager</div>
                            </div>
                            """, unsafe_allow_html=True
                        )
        else:
            st.info("Geen attracties gevonden die aan de filters voldoen.")

# TAB 3: BESTE TIJDEN (RIDE OPTIMIZER MET TIJDSVENSTER)
with tab_best:
    st.subheader("🎯 Ride Optimizer")
    st.caption("Vind het perfecte moment voor jouw favorieten binnen een specifiek tijdsblok.")

    target = active_selection
    
    if not target:
        st.info("👈 Selecteer eerst attracties in de zijbalk.")
    else:
        # 1. TIJDSVENSTER KIEZEN (NIEUW)
        # Slider van 10:00 tot 20:00 (of park sluit)
        scan_window = st.slider(
            "🔎 Zoek beste tijd tussen:",
            min_value=10, 
            max_value=19, 
            value=(12, 16), # Default focus op de middag
            format="%d:00"
        )
        
        start_h, end_h = scan_window
        
        # We scannen INCLUSIEF het einduur (dus 12-15 betekent 12:00, 13:00, 14:00, 15:00)
        hours_range = range(start_h, end_h + 1)
        
        optimization_data = []
        tz = pytz.timezone('Europe/Brussels')
        today = datetime.date.today()

        st.divider()

        with st.spinner(f"Analyseren van {start_h}:00 tot {end_h}:00..."):
            for ride in target:
                trend_list = []
                min_w = 999
                best_h = start_h

                for h in hours_range:
                    query_time = tz.localize(datetime.datetime.combine(today, datetime.time(h, 0)))
                    w = get_wait_time_prediction(park_keuze, ride, query_time, live_data)
                    val = w if isinstance(w, int) else 15
                    
                    trend_list.append(val)
                    
                    # Check of dit het beste moment is BINNEN het venster
                    if val < min_w:
                        min_w = val
                        best_h = h
                
                # Huidige wachttijd ophalen voor vergelijking
                current_val = live_data.get(ride, {}).get('wait_time', 0) if live_data else trend_list[0]
                
                # Besparing berekenen (Verschil tussen NU en het BESTE moment in de gekozen tijd)
                # Als het beste moment in het verleden ligt of gelijk is aan nu, is besparing 0
                saving = max(0, current_val - min_w)
                
                optimization_data.append({
                    "Attractie": ride,
                    "Beste Tijd": f"{best_h}:00",
                    "Min. Wacht": min_w,
                    "Nu": current_val,
                    "Besparing": saving,
                    "Trend": trend_list 
                })

        # 2. VISUALISATIE
        df_opt = pd.DataFrame(optimization_data)
        
        # Sorteer: Waar valt de meeste winst te behalen?
        df_opt = df_opt.sort_values("Besparing", ascending=False)

        st.dataframe(
            df_opt,
            column_order=["Attractie", "Beste Tijd", "Min. Wacht", "Trend", "Besparing"],
            column_config={
                "Attractie": st.column_config.TextColumn("Attractie", width="medium"),
                
                "Beste Tijd": st.column_config.TextColumn(
                    "🏆 Beste Tijd", 
                    help=f"Het beste moment tussen {start_h}:00 en {end_h}:00",
                    width="small"
                ),
                
                "Min. Wacht": st.column_config.NumberColumn(
                    "Verwacht", 
                    format="%d min",
                    help="De voorspelde wachttijd op dat tijdstip",
                ),
                
                "Trend": st.column_config.LineChartColumn(
                    f"Verloop ({start_h}u-{end_h}u)",
                    y_min=0,
                    y_max=60,
                    width="medium",
                    help="Het verloop van de drukte binnen jouw gekozen tijdsvenster."
                ),
                
                "Besparing": st.column_config.ProgressColumn(
                    "Winst vs Nu",
                    format="%d min",
                    min_value=0,
                    max_value=60,
                    help="Hoeveel minuten je bespaart t.o.v. de huidige wachttijd"
                ),
            },
            hide_index=True,
            use_container_width=True
        )

# TAB 4: TOEKOMST (INTELLIGENT PREP)
with tab_future:
    st.header("📅 De Ultieme Voorbereiding")
    st.caption("De app haalt live weersvoorspellingen en historische data op om je dag te simuleren.")

    c1, c2 = st.columns([1, 2])
    fut_date = c1.date_input("Wanneer ga je?", datetime.date.today() + datetime.timedelta(days=1))
    
    weather_data = get_automated_weather(park_keuze, fut_date)
    is_holiday = is_crowd_risk_day(fut_date)

    with c2.container():
        wc1, wc2, wc3 = st.columns(3)
        wc1.metric("Temperatuur", f"{weather_data['temp_c']} °C")
        wc2.metric("Regenkans", f"{weather_data.get('rain_prob', 0)} %")
        wc3.metric("Type Dag", "Vakantie" if is_holiday else "Regulier")
    
    with st.expander("🛠️ Ik weet het beter (Handmatig aanpassen)"):
        sim_temp = st.slider("Temp (°C)", -5, 35, int(weather_data['temp_c']))
        sim_rain_prob = st.slider("Neerslagkans (%)", 0, 100, int(weather_data.get('rain_prob', 0)))
        sim_rain_mm = 2.0 if sim_rain_prob > 40 else 0.0
    
    final_temp = sim_temp if 'sim_temp' in locals() else weather_data['temp_c']
    final_rain_mm = sim_rain_mm if 'sim_rain_mm' in locals() else weather_data['precip_mm']

    st.divider()

    if st.button("🔮 Voorspel de Drukte", type="primary", use_container_width=True):
        with st.spinner("AI berekent scenario's..."):
            top_rides = [r for r, m in all_meta.items() if m.get('score', 0) >= 8 and m.get('type') != 'Restaurant']
            sim_results = []
            hours_range = range(10, 19)
            best_start_ride = None
            min_start_wait = 999
            
            for ride in top_rides:
                total_wait = 0
                count = 0
                
                start_time = datetime.datetime.combine(fut_date, datetime.time(10, 0))
                start_w = get_wait_time_prediction(park_keuze, ride, start_time, weather_override={"temp_c": final_temp, "precip_mm": final_rain_mm, "condition": "Cloudy"})
                if isinstance(start_w, dict): start_w = 15
                
                if start_w < min_start_wait:
                    min_start_wait = start_w
                    best_start_ride = ride

                for h in hours_range:
                    t = datetime.datetime.combine(fut_date, datetime.time(h, 0))
                    w = get_wait_time_prediction(park_keuze, ride, t, weather_override={"temp_c": final_temp, "precip_mm": final_rain_mm, "condition": "Cloudy"})
                    val = w if isinstance(w, int) else 15
                    total_wait += val
                    count += 1
                
                avg = total_wait / count if count > 0 else 0
                sim_results.append({"Attractie": ride, "Gemiddelde Wachttijd": int(avg)})
            
            df_res = pd.DataFrame(sim_results).sort_values("Gemiddelde Wachttijd", ascending=True)
            
            if best_start_ride:
                st.success(f"🚀 **Start-Tip:** Begin je dag bij **{best_start_ride}**! Verwachte wachttijd om 10:00 is slechts **{min_start_wait} min**.")

            avg_wait = df_res['Gemiddelde Wachttijd'].mean()
            if avg_wait < 20: crowd_msg = "🟢 **Conclusie:** Rustige dag. Geniet ervan!"
            elif avg_wait < 45: crowd_msg = "🟠 **Conclusie:** Gemiddelde drukte. Blijf plannen."
            else: crowd_msg = "🔴 **Conclusie:** Erg druk. Focus op je top 3."
            st.info(crowd_msg)

            st.markdown("### 📊 Verwachte Gemiddelde Wachttijden (Hele Dag)")
            fig = px.bar(
                df_res, x="Gemiddelde Wachttijd", y="Attractie", orientation='h', 
                color="Gemiddelde Wachttijd", color_continuous_scale="RdYlGn_r", text_auto=True 
            )
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), xaxis_title="Minuten")
            st.plotly_chart(fig, use_container_width=True)

# TAB 5: PERFECTE ROUTE (NIEUW!)
with tab_perfect:
    st.header("🏆 De 'Fun-Hunter' Modus")
    st.info("Deze modus negeert je lijstje. Hij probeert simpelweg **zoveel mogelijk punten** te scoren binnen de tijd. Grote attracties leveren meer punten op.", icon="ℹ️")
    
    cp1, cp2 = st.columns(2)
    cp1.time_input("Starttijd", value=st.session_state.start_time_val, key="perf_start", on_change=update_start_time)
    cp2.time_input("Eindtijd", value=st.session_state.end_time_val, key="perf_end", on_change=update_end_time)

    if st.button("🚀 Bereken Topscore Route", type="primary"):
        with st.spinner("AI zoekt de ultieme strategie..."):
            s_str = st.session_state.start_time_val.strftime("%H:%M")
            e_str = st.session_state.end_time_val.strftime("%H:%M")
            
            route, _, _ = solve_max_score_route(
                park_name=park_keuze,
                start_str=s_str,
                end_str=e_str,
                start_location=st.session_state.current_loc,
                pace_factor=pace_factor
            )
            
            if not route:
                st.error("Kon geen route vinden. Is het park al dicht?")
            else:
                st.success("🎯 Strategie gevonden! Zie hieronder.")
                for i, step in enumerate(route):
                    label = f"**{step['start_walk']}** | {step['ride']}"
                    with st.expander(label, expanded=(i==0)):
                        c1, c2 = st.columns([1,2])
                        c1.write(f"🚶 Loop: {step['walk_min']} min")
                        c1.write(f"⏳ Wacht: {step['wait_min']} min")
                        c2.info(f"{step['note']}")

# TAB 6: VOLTOOID (DOORGESCHOVEN)
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