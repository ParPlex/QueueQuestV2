import streamlit as st
import datetime
import pandas as pd
import plotly.express as px # Voor mooie grafiekjes
from route_solver import solve_route, get_wait_time_prediction
from queuequest_meta import ATTRACTION_METADATA

# Pagina Config
st.set_page_config(page_title="QueueQuest", page_icon="🎢", layout="wide")

# Titel
col1, col2 = st.columns([1, 4])
with col1:
    st.write("## 🎢")
with col2:
    st.title("QueueQuest AI")
    st.caption("De slimste route door Efteling, Phantasialand & Walibi")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Instellingen")

# Park Selectie
park_keuze = st.sidebar.selectbox(
    "Kies je Park:",
    ("EFTELING", "PHANTASIALAND", "WALIBI_BELGIUM")
)

# Attracties ophalen uit metadata op basis van park
alle_attracties = [name for name, meta in ATTRACTION_METADATA.items() if meta['park'] == park_keuze]
selected_rides = st.sidebar.multiselect(
    "Selecteer je 'Must-Do' attracties:",
    options=sorted(alle_attracties),
    default=sorted(alle_attracties)[:5]
)

# Tijden
col_t1, col_t2 = st.sidebar.columns(2)
start_time = col_t1.time_input("Aankomst", datetime.time(10, 0))
end_time = col_t2.time_input("Vertrek", datetime.time(18, 0))

# --- HOOFDPAGINA ---

if st.sidebar.button("🚀 Bereken Optimale Route", type="primary"):
    if not selected_rides:
        st.error("Kies ten minste één attractie!")
    else:
        start_str = start_time.strftime("%H:%M")
        end_str = end_time.strftime("%H:%M")

        # 1. De AI laten rekenen
        with st.spinner('🤖 AI is aan het puzzelen... (Weer checken, Drukte voorspellen, Looproutes berekenen)'):
            route, total_wait, total_walk = solve_route(park_keuze, selected_rides, start_str, end_str)

        # 2. Resultaten tonen
        st.divider()
        
        # Scorekaart
        m1, m2, m3 = st.columns(3)
        m1.metric("Aantal Attracties", len(selected_rides))
        m2.metric("Totale Wachttijd", f"{total_wait} min")
        m3.metric("Totale Wandeltijd", f"{total_walk} min")

        # Tabs voor weergave
        tab_route, tab_flex, tab_chart = st.tabs(["📍 Jouw Route", "🕒 Flexibele Tijden", "📈 Drukte Grafiek"])

        with tab_route:
            if not route:
                st.warning("Geen route mogelijk binnen deze tijd!")
            else:
                # Mooie tijdlijn weergave
                timeline_data = []
                for step in route:
                    # Loopstukje
                    timeline_data.append({
                        "Tijd": step['start_walk'],
                        "Activiteit": f"🚶 Loop naar {step['ride']}",
                        "Duur": f"{step['walk_min']} min",
                        "Type": "Lopen"
                    })
                    # Wachtstukje
                    note = f" ({step['note']})" if "Optimale" in step['note'] else ""
                    timeline_data.append({
                        "Tijd": step['arrival_time'],
                        "Activiteit": f"⏳ Wachten voor {step['ride']}",
                        "Duur": f"{step['wait_min']} min{note}",
                        "Type": "Wachten"
                    })
                    # Ritstukje
                    timeline_data.append({
                        "Tijd": step['ride_start'],
                        "Activiteit": f"🎢 {step['ride']}!",
                        "Duur": f"Tot {step['ride_end']}",
                        "Type": "Pret"
                    })
                
                st.dataframe(
                    pd.DataFrame(timeline_data), 
                    column_config={
                        "Type": st.column_config.TextColumn("Type", width="small"),
                    },
                    use_container_width=True, 
                    hide_index=True
                )

        with tab_flex:
            st.info("Wil je afwijken? Hier zie je per attractie wanneer de rij het kortst is.")
            
            flex_data = []
            scan_range = range(start_time.hour, end_time.hour + 1)
            now_date = datetime.datetime.now()
            
            for ride in selected_rides:
                min_w = 999
                best_h = -1
                
                for h in scan_range:
                    test_t = now_date.replace(hour=h, minute=0, second=0)
                    w = get_wait_time_prediction(park_keuze, ride, test_t)
                    if w < min_w:
                        min_w = w
                        best_h = h
                
                flex_data.append({
                    "Attractie": ride,
                    "Beste Tijd": f"{best_h}:00",
                    "Verwachte Wachttijd": f"{min_w} min"
                })
            
            st.dataframe(pd.DataFrame(flex_data), hide_index=True, use_container_width=True)

        with tab_chart:
            st.caption("Verwachte drukte verloop voor jouw gekozen attracties")
            
            chart_data = []
            for h in range(start_time.hour, end_time.hour + 1):
                t = now_date.replace(hour=h, minute=0, second=0)
                for ride in selected_rides:
                    w = get_wait_time_prediction(park_keuze, ride, t)
                    chart_data.append({"Uur": f"{h}:00", "Attractie": ride, "Wachttijd": w})
            
            df_chart = pd.DataFrame(chart_data)
            fig = px.line(df_chart, x="Uur", y="Wachttijd", color="Attractie", markers=True)
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Selecteer je attracties in de zijbalk om te beginnen.")