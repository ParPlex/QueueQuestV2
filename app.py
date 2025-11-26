import streamlit as st
import datetime
import pandas as pd
import requests
from route_solver import solve_route_with_priorities, fetch_live_data
from queuequest_meta import ATTRACTION_METADATA

st.set_page_config(page_title="QueueQuest Live", page_icon="🎢", layout="wide")

# Titel en Intro
st.title("🎢 QueueQuest Live Co-Pilot")
st.caption("Real-time optimalisatie met prioriteiten en live data.")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Instellingen")
park_keuze = st.sidebar.selectbox("Kies Park:", ("EFTELING", "PHANTASIALAND", "WALIBI_BELGIUM"))

# Data voorbereiden
alle_rides = sorted([n for n, m in ATTRACTION_METADATA.items() if m['park'] == park_keuze])

# 1. Live Status Check (Vooraf!)
if 'live_data' not in st.session_state or st.sidebar.button("🔄 Ververs Live Data"):
    with st.spinner("Verbinding met park..."):
        st.session_state['live_data'] = fetch_live_data(park_keuze)

live_data = st.session_state.get('live_data', {})

# Toon live storingen direct in sidebar
closed_now = [name for name, data in live_data.items() if not data['is_open'] and name in alle_rides]
if closed_now:
    st.sidebar.error(f"⚠️ Nu Gesloten: {', '.join(closed_now)}")

# 2. Prioriteiten Selectie
st.sidebar.subheader("1. Must Haves (Hoge Prio)")
must_haves = st.sidebar.multiselect("Welke wil je ABSOLUUT doen?", alle_rides)

remaining = [r for r in alle_rides if r not in must_haves]
st.sidebar.subheader("2. Should Haves (Opvulling)")
should_haves = st.sidebar.multiselect("Welke wil je doen als het uitkomt?", remaining)

# 3. Tijden
col1, col2 = st.sidebar.columns(2)
start_time = col1.time_input("Starttijd", datetime.datetime.now().time())
end_time = col2.time_input("Eindtijd", datetime.time(18, 0))

# --- HOOFDSCHERM ---

if st.button("🚀 Bereken Slimme Route", type="primary"):
    if not must_haves and not should_haves:
        st.warning("Kies ten minste één attractie.")
    else:
        start_str = start_time.strftime("%H:%M")
        end_str = end_time.strftime("%H:%M")
        
        with st.spinner("AI is aan het puzzelen..."):
            route, closed, skipped = solve_route_with_priorities(
                park_keuze, must_haves, should_haves, start_str, end_str
            )
        
        # Resultaten
        st.subheader("📍 Jouw Optimale Route")
        
        if closed:
            st.warning(f"🚫 Deze attracties zijn gesloten en uit de route gehaald: {', '.join(closed)}")
        
        if route:
            timeline = []
            tot_wait = 0
            tot_walk = 0
            
            for step in route:
                icon = "⭐" if step['type'] == "MUST" else "🔹"
                timeline.append({
                    "Tijd": step['start_walk'],
                    "Activiteit": f"🚶 Loop naar {step['ride']}",
                    "Duur": f"{step['walk_min']} min",
                    "Prio": ""
                })
                timeline.append({
                    "Tijd": step['arrival_time'],
                    "Activiteit": f"⏳ Wachten voor {step['ride']}",
                    "Duur": f"{step['wait_min']} min",
                    "Prio": step['note']
                })
                timeline.append({
                    "Tijd": step['ride_start'],
                    "Activiteit": f"🎢 {icon} {step['ride']}",
                    "Duur": f"Tot {step['ride_end']}",
                    "Prio": step['type']
                })
                tot_wait += step['wait_min']
                tot_walk += step['walk_min']

            # Scorebord
            c1, c2, c3 = st.columns(3)
            c1.metric("Attracties", len(route))
            c2.metric("Wachttijd", f"{tot_wait} min")
            c3.metric("Wandeltijd", f"{tot_walk} min")
            
            st.dataframe(pd.DataFrame(timeline), use_container_width=True, hide_index=True)
            
            if skipped:
                st.info(f"💡 Overgeslagen (wegens tijd/drukte): {', '.join(skipped)}")
        else:
            st.error("Geen route mogelijk binnen deze tijd!")

else:
    st.info("👈 Selecteer je prioriteiten links en druk op de knop.")