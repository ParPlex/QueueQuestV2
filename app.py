import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
import numpy as np
import importlib
import pytz 

# Force reload of route_solver on every interaction
import route_solver
importlib.reload(route_solver)

# Import BOTH solvers
from route_solver import solve_route_with_priorities, solve_max_score_route, fetch_live_data, get_wait_time_prediction
from queuequest_meta import ATTRACTION_METADATA
from holiday_utils import is_crowd_risk_day

# Try to load weather_utils
try:
    from weather_utils import get_automated_weather
except ImportError:
    # Fallback function if file is missing
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

# --- FUNCTIONS FOR EXPLANATION & STRATEGY (CACHED) ---

@st.cache_data(show_spinner=False)
def generate_strategy_explanation(route, park_name):
    """Generates a logical explanation for the chosen route (English)."""
    if not route: return None, None
    
    first_ride = route[0]['ride']
    rides_only = [r for r in route if r['type'] != 'LUNCH']
    total_walk = sum(r['walk_min'] for r in rides_only)
    avg_walk = total_walk / len(rides_only) if rides_only else 0
    
    # List of 'Morning Killers'
    headliners = {
        "EFTELING": ["Baron 1898", "Symbolica", "De Vliegende Hollander", "Joris en de Draak"],
        "PHANTASIALAND": ["Taron", "F.L.Y.", "Black Mamba", "Maus au Chocolat"],
        "WALIBI_BELGIUM": ["Kondaa", "Pulsar", "Psyké Underground"]
    }
    
    # SCENARIO 1: The Rocket Start
    if park_name in headliners and any(h in first_ride for h in headliners[park_name]):
        return "🚀 The 'Rocket Start' Strategy", f"We are sending you straight to **{first_ride}**. This is a top-tier attraction; doing it now will likely save you 30+ minutes compared to later."

    # SCENARIO 2: The Efficient Walker
    if avg_walk < 4: 
        return "👟 The 'Efficient Walker' Strategy", "This route bundles attractions that are close together. Walking time is minimized, leaving more time for rides and breaks."

    # SCENARIO 3: The 'Ramp Up'
    if route[0]['wait_min'] <= 10:
        return "📈 The 'Ramp Up' Strategy", f"We start calmly at **{first_ride}** to bag an immediate win with a short queue. The busier rides are planned for later."

    # DEFAULT
    return "⚖️ The 'Balanced' Strategy", "This order calculates the optimal mix between prioritizing your Must-Haves and avoiding walking back and forth too much."

def get_step_reason(step, prev_step_loc, park_name, live_data):
    """
    Determines the reason and calculates 'Opportunity Cost'.
    """
    ride = step['ride']
    
    # Check for Score Mode (might not have wait_min directly available in all cases)
    wait_now = step.get('wait_min', 0)
    walk = step.get('walk_min', 0)
    
    # 1. Is it Lunch?
    if step['type'] == 'LUNCH':
        return "🍽️ Time to recharge."
    
    # 2. Is it a Score Run?
    if step['type'] == 'SCORE':
        return "💎 **Score Booster:** This ride currently offers the best value (fun/time ratio)."

    # 3. FUTURE ANALYSIS
    try:
        tz = pytz.timezone('Europe/Brussels')
        now = datetime.datetime.now(tz)
        today = now.date()
        h, m = map(int, step['arrival_time'].split(':'))
        arrival_dt = tz.localize(datetime.datetime.combine(today, datetime.time(h, m)))
        
        # Look 2 hours into the future
        future_check_time = arrival_dt + datetime.timedelta(hours=2)
        
        # Predict wait time in future
        wait_later = get_wait_time_prediction(park_name, ride, future_check_time, live_data_snapshot=None)
        if isinstance(wait_later, dict): wait_later = 15
        
        time_saved = wait_later - wait_now
        
    except:
        time_saved = 0

    # --- THE STRATEGY RULES ---

    # RULE A: The "Master Move"
    if time_saved >= 15:
        return f"📉 **Smart Move:** Wait times here will rise to approx. {wait_later} min later. **You save {time_saved} min** by going now."

    # RULE B: The "Early Bird"
    headliners = ["Baron 1898", "Symbolica", "Joris en de Draak", "Taron", "F.L.Y.", "Black Mamba", "Kondaa"]
    if any(h in ride for h in headliners) and wait_now < 15:
        return f"⚡ **Opportunity:** Top attraction with only {wait_now} min wait. Catch it while you can!"

    # RULE C: The "Neighbor"
    if walk <= 3 and prev_step_loc != "Ingang":
        extra_msg = ""
        if time_saved > 5: extra_msg = f" (And you save {time_saved} min vs this afternoon)"
        return f"📍 **Proximity:** It's practically next door to your previous location.{extra_msg}"

    # RULE D: The "Quick Win"
    if step['type'] == "SHOULD" and wait_now <= 5:
        return "👌 **Filler:** Minimal wait time, so perfect to 'pick up' on the way to the next big one."

    # RULE E: Consistency
    if time_saved >= 5:
        return f"✅ **Good Timing:** It is {time_saved} min quieter now than the afternoon average."

    return "⚖️ **Route Optimization:** Fits best in your schedule right now."
    

# --- 1. STATE INITIALIZATION ---
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

# --- 2. INTELLIGENT TIME INITIALIZATION ---
if 'start_time_val' not in st.session_state:
    tz = pytz.timezone('Europe/Brussels')
    now = datetime.datetime.now(tz)
    
    # Check: Is it between 10:00 and 18:00?
    if 10 <= now.hour < 18:
        st.session_state.start_time_val = now.time().replace(second=0, microsecond=0)
    else:
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
    
    # Update time to NOW
    tz = pytz.timezone('Europe/Brussels')
    st.session_state.start_time_val = datetime.datetime.now(tz).time()

st.title("🎢 QueueQuest Ultimate")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Settings")
park_keuze = st.sidebar.selectbox("Park:", ("EFTELING", "PHANTASIALAND", "WALIBI_BELGIUM"))

all_meta = {k: v for k, v in ATTRACTION_METADATA.items() if v['park'] == park_keuze}
rides_all = sorted([r for r, m in all_meta.items() if m.get('type') not in ['Restaurant', 'Snack'] and "Single-rider" not in r])
restaurants = sorted([r for r, m in all_meta.items() if m.get('type') in ['Restaurant', 'Snack']])

st.sidebar.subheader("📍 Location")
loc_options = ["Ingang"] + rides_all + restaurants
if st.session_state.current_loc not in loc_options: st.session_state.current_loc = "Ingang"
st.sidebar.selectbox("You are currently at:", loc_options, key="current_loc")

# --- PACING PROFILE (SLIDER) ---
st.sidebar.subheader("🏃 Walking Pace")
pace_select = st.sidebar.select_slider(
    "How fast do you walk?",
    options=["Relaxed 🐢", "Average 🚶", "Rushing 🐇"],
    value="Average 🚶"
)
# Translate selection to factor
pace_map = {"Relaxed 🐢": 1.4, "Average 🚶": 1.0, "Rushing 🐇": 0.7}
pace_factor = pace_map[pace_select]

# --- SELECTION ---
st.sidebar.subheader("🎯 Wishlist")
keys_to_clean = ['mc', 'sc', 'md', 'sd', 'mo', 'so']
for k in keys_to_clean:
    if st.session_state.completed:
        st.session_state[k] = [x for x in st.session_state[k] if x not in st.session_state.completed]

coasters = [r for r in rides_all if all_meta[r].get('type') in ['Coaster', 'WaterCoaster']]
darkrides = [r for r in rides_all if all_meta[r].get('type') in ['DarkRide', 'Madhouse', 'Cinema']]
others = [r for r in rides_all if r not in coasters and r not in darkrides]

with st.sidebar.expander("🎢 Rollercoasters", expanded=True):
    st.multiselect("Must-Haves", coasters, key="mc")
    remain_c = [r for r in coasters if r not in st.session_state.mc]
    st.multiselect("Fillers", remain_c, key="sc")

with st.sidebar.expander("👻 Darkrides & Shows"):
    st.multiselect("Must-Haves", darkrides, key="md")
    remain_d = [r for r in darkrides if r not in st.session_state.md]
    st.multiselect("Fillers", remain_d, key="sd")

with st.sidebar.expander("🎡 Others"):
    st.multiselect("Must-Haves", others, key="mo")
    remain_o = [r for r in others if r not in st.session_state.mo]
    st.multiselect("Fillers", remain_o, key="so")

# --- AGGREGATION ---
must_haves = st.session_state.mc + st.session_state.md + st.session_state.mo
should_haves = st.session_state.sc + st.session_state.sd + st.session_state.so

# Lunch
st.sidebar.markdown("---")
with st.sidebar.expander("🍔 Lunch Break"):
    want_lunch = st.checkbox("Plan lunch?", value=not st.session_state.lunch_done)
    if want_lunch and not st.session_state.lunch_done:
        l_time = st.time_input("What time?", datetime.time(12, 30))
        l_dur = st.number_input("Minutes", 15, 120, 45, step=15)
        l_rest = st.selectbox("Where?", restaurants)
        lunch_config = {'time': l_time, 'duration': l_dur, 'restaurant': l_rest}
    else:
        lunch_config = None
        if st.session_state.lunch_done: st.sidebar.success("Lunch finished! ✅")

# Live data button
if st.sidebar.button("🔄 Refresh Live Data"):
    st.cache_data.clear()
    with st.spinner("Connecting to park servers..."):
        st.session_state.live_data = fetch_live_data(park_keuze)
live_data = st.session_state.get('live_data', {})

active_selection = must_haves + should_haves
is_park_closed = len(live_data) > 0 and len([r for r in live_data.values() if r['is_open']]) < 3
if not is_park_closed and live_data:
    closed_now = [r for r in active_selection if r in live_data and not live_data[r]['is_open']]
    if closed_now: st.sidebar.error(f"⛔ Closed Now: {', '.join(closed_now)}")
elif is_park_closed: st.sidebar.info("ℹ️ Park Closed (Forecast Mode)")

# --- WAIT OR GO ADVISOR (SIDEBAR) ---
if not is_park_closed and active_selection:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 Wait or Go?")
    
    # Analyze Must-Haves
    targets = st.session_state.mc + st.session_state.md + st.session_state.mo
    
    if not targets:
        st.sidebar.caption("Select 'Must-Haves' for advice.")
    else:
        tz = pytz.timezone('Europe/Brussels')
        now_advice = datetime.datetime.now(tz)
        future_advice = now_advice + datetime.timedelta(minutes=45) 
        
        advice_count = 0
        
        for ride in targets:
            if ride not in live_data or not live_data[ride]['is_open']:
                continue
                
            current_w = live_data[ride]['wait_time']
            
            # Forecast
            future_w = get_wait_time_prediction(park_keuze, ride, future_advice, live_data_snapshot=None)
            if isinstance(future_w, dict): future_w = 15
            
            diff = future_w - current_w
            
            # Advice Logic
            if diff >= 10:
                st.sidebar.success(f"🏃 **RUN to {ride}!**\n\nNow: {current_w}m ➝ Later: {future_w}m\n*(Save {diff} min)*")
                advice_count += 1
            elif diff <= -10:
                st.sidebar.warning(f"☕ **Wait with {ride}**\n\nNow: {current_w}m ➝ Later: {future_w}m\n*(Drops by {abs(diff)} min)*")
                advice_count += 1
        
        if advice_count == 0:
            st.sidebar.info("No drastic changes predicted.")


# --- TABS ---
tab_copilot, tab_radar, tab_best, tab_future, tab_perfect, tab_done = st.tabs([
    "📍 Live Route", 
    "⚡ Radar", 
    "📊 Best Times", 
    "📅 Future", 
    "🏆 Perfect Route", 
    "✅ Done"
])

# TAB 1: CO-PILOT
with tab_copilot:
    c1, c2 = st.columns(2)
    c1.time_input("Start Time", value=st.session_state.start_time_val, key="widget_start_time", on_change=update_start_time)
    c2.time_input("End Time", value=st.session_state.end_time_val, key="widget_end_time", on_change=update_end_time)
    
    if st.button("🚀 Calculate Route", type="primary", use_container_width=True):
        if not active_selection and not lunch_config:
            st.warning("Please select attractions in the sidebar first.")
        else:
            with st.spinner("AI is calculating route..."):
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
            st.error(f"⛔ Closed: {', '.join(st.session_state.last_closed)}")

        strat_title, strat_msg = generate_strategy_explanation(route, park_keuze)
        if strat_title:
            st.info(f"**{strat_title}**\n\n{strat_msg}", icon="🧠")

        rides_only = [r for r in route if r['type'] != 'LUNCH']
        ai_wait = sum(s['wait_min'] for s in rides_only)
        m1, m2, m3 = st.columns(3)
        m1.metric("Rides", len(rides_only))
        m2.metric("Total Wait", f"{ai_wait} min")
        m3.metric("Next Up", route[0]['ride'] if route else "Done")

        st.subheader("👇 Your Plan")
        prev_loc = st.session_state.current_loc 

        for i, step in enumerate(route):
            is_next = (i == 0)
            icon = "🎢"
            if step['type'] == "LUNCH": icon = "🍔"
            elif "Coaster" in ATTRACTION_METADATA.get(step['ride'], {}).get('type', ''): icon = "🎢"
            elif "DarkRide" in ATTRACTION_METADATA.get(step['ride'], {}).get('type', ''): icon = "👻"
            
            label = f"**{step['start_walk']}** | {icon} Go to {step['ride']}"
            if is_next: label = "👉 " + label

            with st.expander(label, expanded=is_next):
                c1, c2, c3 = st.columns([2,2,1])
                reason_msg = get_step_reason(step, prev_loc, park_keuze, live_data)
                
                # --- LOGIC FIX: TIME HORIZON CHECK ---
                try:
                    # 1. Get Simulation Start Time (from Widget)
                    sim_start = st.session_state.start_time_val
                    dummy_date = datetime.date.today()
                    dt_start = datetime.datetime.combine(dummy_date, sim_start)
                    
                    # 2. Get Step Time
                    h, m = map(int, step['start_walk'].split(':'))
                    dt_step = datetime.datetime.combine(dummy_date, datetime.time(h, m))
                    
                    # 3. Calculate difference in minutes
                    diff_min = (dt_step - dt_start).total_seconds() / 60
                    
                    # 4. Decision: If step is > 30 mins away, FORCE Forecast
                    if diff_min > 30:
                        source_label = "Forecast"
                        source_icon = "🔮"
                    elif "Live" in step.get('note', ''):
                        source_label = "Live Data"
                        source_icon = "📡"
                    else:
                        source_label = "Forecast"
                        source_icon = "🔮"
                except:
                    # Fallback if time parsing fails
                    source_label = "Forecast"
                    source_icon = "🔮"
                # -------------------------------------

                if step['type'] == "LUNCH":
                    c1.write(f"🚶 Walk: {step['walk_min']} min")
                    c2.info(f"{reason_msg}\n\n*Duration: {step['note']}*")
                    if c3.button("✅ Ate!", key=f"lunch_{i}"):
                        st.session_state.lunch_done = True
                        st.session_state.current_loc = step['ride'].replace("🍽️ Lunch: ", "")
                        st.session_state.last_route = None
                        tz = pytz.timezone('Europe/Brussels')
                        st.session_state.start_time_val = datetime.datetime.now(tz).time()
                        st.rerun()
                else:
                    c1.write(f"🚶 Walk: {step['walk_min']} min")
                    c1.write(f"⏳ Wait: {step['wait_min']} min")
                    
                    prio_label = " | ⭐ Must-Do" if step['type'] == "MUST" else ""
                    
                    # Updated info box with corrected source label
                    c2.info(f"{reason_msg}\n\n*({source_icon} {source_label}{prio_label})*")
                    
                    c3.button("✅ Done!", key=f"done_{step['ride']}_{i}", on_click=mark_done, args=(step['ride'],))
            prev_loc = step['ride']

    elif st.session_state.last_route == []:
        if st.session_state.last_closed:
            st.error("⛔ No route possible: All selected attractions are closed!")
            st.write("The following rides are closed:")
            for c in st.session_state.last_closed:
                st.write(f"- 🔴 {c}")
        elif not active_selection:
            st.warning("👈 Select attractions in the sidebar first.")
        else:
            st.success("🎉 All done! You have finished your list.")

# TAB 2: MARKET ANALYSIS (MARKET WATCH)
with tab_radar:
    st.subheader("📉 Market Watch: Opportunities & Traps")
    
    # --- 1. CONFIGURATION & FILTERS ---
    c_filters, c_info = st.columns([2, 2])
    
    with c_filters:
        benchmark_mode = st.radio(
            "Compare with:", 
            ["🤖 AI Expectation (Today)", "📊 Yearly Average"],
            horizontal=True,
            label_visibility="collapsed"
        )
        score_filter = st.select_slider(
            "Filter by Quality:",
            options=["All", "From 6 (Good)", "8+ (Top Tier)"],
            value="All"
        )

    if benchmark_mode.startswith("🤖"):
        c_info.info("💡 **AI Mode:** Compares live crowds with the prediction for *today*.")
    else:
        c_info.info("💡 **Historical:** Compares live crowds with the *yearly average*.")

    st.divider()

    if not live_data:
        st.warning("No live data available. Press '🔄 Refresh Live Data' in the sidebar.")
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
            
            if score_filter == "From 6 (Good)" and score < 6: continue
            if score_filter == "8+ (Top Tier)" and score < 8: continue

            if "AI" in benchmark_mode:
                predicted = get_wait_time_prediction(park_keuze, ride_name, now_radar, live_data_snapshot=None)
                if isinstance(predicted, dict): predicted = 20
                norm_wait = predicted
            else:
                norm_wait = historical_averages.get(ride_name, curr_wait) 
            
            diff = norm_wait - curr_wait 
            
            if norm_wait > 5 or curr_wait > 5:
                market_data.append({
                    "Attraction": ride_name,
                    "Now": curr_wait,
                    "Normal": norm_wait, 
                    "Gain": diff,
                    "Score": score
                })
        
        df_market = pd.DataFrame(market_data)

        if not df_market.empty:
            st.markdown("### 🎯 Opportunity Matrix")
            fig = px.scatter(
                df_market,
                x="Normal",
                y="Gain",
                color="Gain",
                size="Score", 
                text="Attraction",
                color_continuous_scale="RdYlGn", 
                range_color=[-20, 20],
                labels={"Normal": "Normal Crowds", "Gain": "Minutes Saved"},
                height=450
            )
            
            fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Average")
            fig.update_traces(textposition='top center', marker=dict(line=dict(width=1, color='DarkSlateGrey')))
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", 
                paper_bgcolor="rgba(0,0,0,0)", 
                font=dict(color="white"),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.caption(f"Guide: Top-right are top rides that are quiet now. (Filter active: {score_filter})")

            st.divider()

            c_win, c_loss = st.columns(2)
            
            with c_win:
                st.subheader("🟢 Do Now (Faster)")
                winners = df_market[df_market['Gain'] >= 5].sort_values("Gain", ascending=False)
                if winners.empty: st.caption("No bargains found.")
                else:
                    for _, row in winners.iterrows():
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(30, 200, 80, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 8px; border-left: 4px solid #4CAF50;">
                                <div style="font-weight: bold; font-size: 1.1em;">{row['Attraction']} <span style="font-size:0.8em; color:#AAA;">(⭐{row['Score']})</span></div>
                                <div style="display: flex; justify-content: space-between;">
                                    <span>Now: <b style="color: #4CAF50;">{row['Now']} min</b></span>
                                    <span style="color: #AAA;">(Normal: {row['Normal']})</span>
                                </div>
                                <div style="font-size: 0.9em; color: #4CAF50;">▼ {row['Gain']} min gain</div>
                            </div>
                            """, unsafe_allow_html=True
                        )

            with c_loss:
                st.subheader("🔴 Avoid Now (Slower)")
                losers = df_market[df_market['Gain'] <= -5].sort_values("Gain", ascending=True)
                if losers.empty: st.caption("No major traffic jams.")
                else:
                    for _, row in losers.iterrows():
                        extra_time = abs(row['Gain'])
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(255, 80, 80, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 8px; border-left: 4px solid #FF5252;">
                                <div style="font-weight: bold; font-size: 1.1em;">{row['Attraction']} <span style="font-size:0.8em; color:#AAA;">(⭐{row['Score']})</span></div>
                                <div style="display: flex; justify-content: space-between;">
                                    <span>Now: <b style="color: #FF5252;">{row['Now']} min</b></span>
                                    <span style="color: #AAA;">(Normal: {row['Normal']})</span>
                                </div>
                                <div style="font-size: 0.9em; color: #FF5252;">▲ {extra_time} min slower</div>
                            </div>
                            """, unsafe_allow_html=True
                        )
        else:
            st.info("No attractions found matching criteria.")

# TAB 3: BEST TIMES (RIDE OPTIMIZER WITH TIME WINDOW)
with tab_best:
    st.subheader("🎯 Ride Optimizer")
    st.caption("Find the perfect moment for your favorites within a specific time window.")

    target = active_selection
    
    if not target:
        st.info("👈 Select attractions in the sidebar first.")
    else:
        # 1. TIME WINDOW SELECTION
        scan_window = st.slider(
            "🔎 Search best time between:",
            min_value=10, 
            max_value=19, 
            value=(12, 16),
            format="%d:00"
        )
        
        start_h, end_h = scan_window
        hours_range = range(start_h, end_h + 1)
        
        optimization_data = []
        tz = pytz.timezone('Europe/Brussels')
        today = datetime.date.today()

        st.divider()

        with st.spinner(f"Analyzing from {start_h}:00 to {end_h}:00..."):
            for ride in target:
                trend_list = []
                min_w = 999
                best_h = start_h

                for h in hours_range:
                    query_time = tz.localize(datetime.datetime.combine(today, datetime.time(h, 0)))
                    w = get_wait_time_prediction(park_keuze, ride, query_time, live_data)
                    val = w if isinstance(w, int) else 15
                    
                    trend_list.append(val)
                    
                    if val < min_w:
                        min_w = val
                        best_h = h
                
                current_val = live_data.get(ride, {}).get('wait_time', 0) if live_data else trend_list[0]
                saving = max(0, current_val - min_w)
                
                optimization_data.append({
                    "Attraction": ride,
                    "Best Time": f"{best_h}:00",
                    "Min. Wait": min_w,
                    "Now": current_val,
                    "Saving": saving,
                    "Trend": trend_list 
                })

        # 2. VISUALIZATION
        df_opt = pd.DataFrame(optimization_data)
        df_opt = df_opt.sort_values("Saving", ascending=False)

        st.dataframe(
            df_opt,
            column_order=["Attraction", "Best Time", "Min. Wait", "Trend", "Saving"],
            column_config={
                "Attraction": st.column_config.TextColumn("Attraction", width="medium"),
                
                "Best Time": st.column_config.TextColumn(
                    "🏆 Best Time", 
                    help=f"The best moment between {start_h}:00 and {end_h}:00",
                    width="small"
                ),
                
                "Min. Wait": st.column_config.NumberColumn(
                    "Expect", 
                    format="%d min",
                    help="Predicted wait time at that hour",
                ),
                
                "Trend": st.column_config.LineChartColumn(
                    f"Trend ({start_h}h-{end_h}h)",
                    y_min=0,
                    y_max=60,
                    width="medium",
                    help="Crowd trend within your window."
                ),
                
                "Saving": st.column_config.ProgressColumn(
                    "Gain vs Now",
                    format="%d min",
                    min_value=0,
                    max_value=60,
                    help="Minutes saved compared to going right now"
                ),
            },
            hide_index=True,
            use_container_width=True
        )

# TAB 4: FUTURE (INTELLIGENT PREP)
# TAB 4: FUTURE (INTELLIGENT PREP)
with tab_future:
    st.header("📅 The Ultimate Prep")
    st.caption("The app retrieves live weather forecasts and historical data to simulate your day.")

    c1, c2 = st.columns([1, 2])
    fut_date = c1.date_input("When are you visiting?", datetime.date.today() + datetime.timedelta(days=1))
    
    weather_data = get_automated_weather(park_keuze, fut_date)
    is_holiday = is_crowd_risk_day(fut_date)

    with c2.container():
        wc1, wc2, wc3 = st.columns(3)
        wc1.metric("Temperature", f"{weather_data['temp_c']} °C")
        wc2.metric("Rain Probability", f"{weather_data.get('rain_prob', 0)} %")
        wc3.metric("Day Type", "Holiday" if is_holiday else "Regular")
    
    with st.expander("🛠️ Manual Override"):
        sim_temp = st.slider("Temp (°C)", -5, 35, int(weather_data['temp_c']))
        sim_rain_prob = st.slider("Precip Chance (%)", 0, 100, int(weather_data.get('rain_prob', 0)))
        sim_rain_mm = 2.0 if sim_rain_prob > 40 else 0.0
    
    final_temp = sim_temp if 'sim_temp' in locals() else weather_data['temp_c']
    final_rain_mm = sim_rain_mm if 'sim_rain_mm' in locals() else weather_data['precip_mm']

    st.divider()

    if st.button("🔮 Predict Crowds", type="primary", use_container_width=True):
        with st.spinner("AI calculating scenarios..."):
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
                sim_results.append({"Attraction": ride, "Average Wait": int(avg)})
            
            df_res = pd.DataFrame(sim_results).sort_values("Average Wait", ascending=True)
            
            if best_start_ride:
                st.success(f"🚀 **Start Tip:** Begin your day at **{best_start_ride}**! Expected wait at 10:00 is only **{min_start_wait} min**.")

            avg_wait = df_res['Average Wait'].mean()
            if avg_wait < 20: crowd_msg = "🟢 **Conclusion:** Quiet day. Enjoy!"
            elif avg_wait < 45: crowd_msg = "🟠 **Conclusion:** Average crowds. Keep planning."
            else: crowd_msg = "🔴 **Conclusion:** Busy day. Focus on top 3."
            st.info(crowd_msg)

            st.markdown("### 📊 Expected Average Waits (All Day)")
            
            # --- COLOR SCALE UPDATE ---
            # Using the app's native palette: Blue (#4A90E2) to Gold (#FFC107)
            fig = px.bar(
                df_res, 
                x="Average Wait", 
                y="Attraction", 
                orientation='h', 
                color="Average Wait", 
                # Custom scale: Low Wait = Blue, High Wait = Gold
                color_continuous_scale=[(0, "#4A90E2"), (1, "#FFC107")], 
                range_color=[0, 60], 
                text_auto=True 
            )
            # --------------------------
            
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), xaxis_title="Minutes")
            st.plotly_chart(fig, use_container_width=True)
# TAB 5: PERFECT ROUTE (Fun-Hunter & Completionist)
with tab_perfect:
    st.header("🏆 The 'Fun-Hunter' Modes")
    
    # 1. Tijd Instellingen
    cp1, cp2 = st.columns(2)
    cp1.time_input("Start Time", value=st.session_state.start_time_val, key="perf_start", on_change=update_start_time)
    cp2.time_input("End Time", value=st.session_state.end_time_val, key="perf_end", on_change=update_end_time)

    st.markdown("---")

    # 2. De Toggle (Keuzemenu)
    mode_selection = st.radio(
        "Choose your challenge:",
        ["💎 High Score Run", "🏁 Challenge: Do All Rides"],
        horizontal=True,
        help="High Score focuses on quality/points. Do All Rides tries to empty the checklist."
    )

    # Dynamische uitleg en knop tekst op basis van keuze
    if mode_selection == "💎 High Score Run":
        st.caption("ℹ️ **Strategy:** Ignores your wishlist. Simply tries to gather **max points** (Quality/Time ratio) within the timeframe.")
        btn_label = "🚀 Calculate Top Score Route"
    else:
        st.caption("ℹ️ **Strategy:** Ignores your wishlist. Tries to visit **every single attraction** available in the park.")
        btn_label = "🌍 Calculate Full Loop"

    # 3. De Actie Knop
    if st.button(btn_label, type="primary", use_container_width=True):
        
        s_str = st.session_state.start_time_val.strftime("%H:%M")
        e_str = st.session_state.end_time_val.strftime("%H:%M")

        # --- LOGICA VOOR HIGH SCORE ---
        if mode_selection == "💎 High Score Run":
            with st.spinner("AI finding winning strategy..."):
                route, _, _ = solve_max_score_route(
                    park_name=park_keuze,
                    start_str=s_str,
                    end_str=e_str,
                    start_location=st.session_state.current_loc,
                    pace_factor=pace_factor
                )
                
                if not route:
                    st.error("No route found. Park closed or time window too short?")
                else:
                    # RIDE COUNTER (De nieuwe feature)
                    ride_count = len(route)
                    total_wait = sum(s['wait_min'] for s in route)
                    
                    st.success("🎯 Strategy Found!")
                    
                    # Metrics tonen
                    m1, m2 = st.columns(2)
                    m1.metric("🎢 Rides Scored", ride_count)
                    m2.metric("⏳ Total Wait", f"{total_wait} min")
                    
                    st.markdown("### 📝 The Plan")
                    for i, step in enumerate(route):
                        label = f"**{step['start_walk']}** | {step['ride']}"
                        with st.expander(label, expanded=(i==0)):
                            c1, c2 = st.columns([1,2])
                            c1.write(f"🚶 Walk: {step['walk_min']} min")
                            c1.write(f"⏳ Wait: {step['wait_min']} min")
                            c2.info(f"{step['note']}")

        # --- LOGICA VOOR COMPLETIONIST (DO ALL) ---
        else:
            with st.spinner("Calculating the ultimate loop..."):
                # 1. Alles ophalen behalve eten
                all_rides_target = [r for r, m in all_meta.items() if m.get('type') not in ['Restaurant', 'Snack']]
                # 2. Verwijderen wat al gedaan is
                remaining_target = [r for r in all_rides_target if r not in st.session_state.completed]
                
                if not remaining_target:
                    st.success("You have already done everything! Go home! 😂")
                else:
                    # 3. Solver aanroepen met ALLES als Must-Have
                    route, closed, skipped = solve_route_with_priorities(
                        park_name=park_keuze,
                        must_haves=remaining_target, # Forceer alles
                        should_haves=[],
                        start_str=s_str,
                        end_str=e_str, 
                        start_location=st.session_state.current_loc,
                        lunch_config=None,
                        pace_factor=pace_factor 
                    )
                    
                    if not route and not skipped:
                        st.error("Time window too short to start.")
                    else:
                        st.success(f"🗺️ Loop Calculated!")
                        
                        # Metrics
                        done_count = len(route)
                        skipped_count = len(skipped)
                        total_goal = len(remaining_target)
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("✅ Possible", f"{done_count}/{total_goal}")
                        m2.metric("❌ Skipped", skipped_count)
                        m3.metric("📅 Finish Time", route[-1]['arrival_time'] if route else "-")

                        # Waarschuwing als niet alles past
                        if skipped:
                            st.warning(f"⚠️ Not enough time for: {', '.join(skipped)}")
                        
                        for i, step in enumerate(route):
                             with st.expander(f"{i+1}. {step['ride']} (@ {step['start_walk']})"):
                                st.write(f"Wait: {step['wait_min']}m | Walk: {step['walk_min']}m")

# TAB 6: DONE
with tab_done:
    if st.session_state.completed:
        st.success(f"Already finished {len(st.session_state.completed)} rides!")
        cols = st.columns(3)
        for i, r in enumerate(st.session_state.completed):
            cols[i % 3].success(f"✅ {r}")
        if st.button("🗑️ Reset All"):
            for k in st.session_state.keys(): del st.session_state[k]
            st.rerun()
    else:
        st.info("Nothing finished yet.")