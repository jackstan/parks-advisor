import datetime as dt

import pandas as pd
import streamlit as st

from src.models import TripRequest, WeatherDay, Alert
from src.advisor_llm import advise_trip_with_explanation
from src.advisor_context import build_trip_context
from src.config import PARKS


def score_badge(label: str, value: float) -> str:
    """
    Return a little colored badge as HTML based on the score.
    High (>=80) = green, medium (60–79) = yellow, low (<60) = red.
    """
    if value >= 80:
        color = "#15803d"  # green-700
        text = "Good"
    elif value >= 60:
        color = "#ca8a04"  # yellow-600
        text = "Moderate"
    else:
        color = "#b91c1c"  # red-700
        text = "Risky"

    return (
        f"<div style='display:inline-block;"
        f"margin-top:0.25rem;"
        f"padding:0.1rem 0.5rem;"
        f"border-radius:999px;"
        f"background-color:{color};"
        f"color:white;"
        f"font-size:0.8rem;"
        f"font-weight:600;'>"
        f"{text}</div>"
    )


def main():
    st.set_page_config(
        page_title="Parks Advisor",
        page_icon="🏞️",
        layout="centered",
    )

    st.title("🏞️ Parks Advisor")
    st.write(
        "Trip-planning and safety advisor for Yosemite, using live weather, NPS alerts, "
        "and official NPS content."
    )

    # --- Trip inputs ---------------------------------------------------------
    st.subheader("Trip details")

    
    # Park selection (locked to Yosemite for now)
    if "yose" not in PARKS:
        st.error("PARKS config is missing the 'yose' park code.")
        st.stop()

    park_code = st.selectbox(
        "Park",
        options=["yose"],
        index=0,
        format_func=lambda code: PARKS[code]["name"],
        disabled=True,
    )   
    st.caption("Currently optimized for Yosemite National Park.")


    today = dt.date.today()
    max_forecast_day = today + dt.timedelta(days=16)

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start date",
            value=today + dt.timedelta(days=3),
            min_value=today,
            max_value=max_forecast_day,
            help="Weather-based scoring is most reliable within ~16 days from today.",
        )
    with col2:
        end_date = st.date_input(
            "End date",
            value=today + dt.timedelta(days=5),
            min_value=start_date,
            max_value=max_forecast_day,
        )

    activity_type = st.selectbox(
        "Primary activity",
        ["hiking", "backpacking", "sightseeing"],
        index=0,
    )

    hiker_profile = st.selectbox(
        "Hiker profile",
        ["beginner", "intermediate", "advanced"],
        index=1,
    )

    max_hike_hours = st.slider(
        "Max hiking time per day (hours)",
        min_value=1,
        max_value=12,
        value=6,
    )

    st.markdown("---")

    if st.button("Get trip advice"):
        with st.spinner("Analyzing conditions and NPS info..."):
            trip = TripRequest(
                park_code=park_code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                activity_type=activity_type,
                hiker_profile=hiker_profile,
                constraints={"max_hike_hours": max_hike_hours},
            )

            # Get full context (weather + alerts) for UI
            context = build_trip_context(trip)
            weather_days = context.get("weather", [])
            alerts = context.get("alerts", [])

            # Call the advisor for scores + explanation + prompt
            scores, explanation, prompt_debug = advise_trip_with_explanation(trip)

        # --- Scores card -----------------------------------------------------
        st.subheader("Trip scores")

        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            st.metric("Access score", f"{scores.access_score:.0f}/100")
            st.markdown(
                score_badge("Access score", scores.access_score),
                unsafe_allow_html=True,
            )
        with col_b:
            st.metric("Weather score", f"{scores.weather_score:.0f}/100")
            st.markdown(
                score_badge("Weather score", scores.weather_score),
                unsafe_allow_html=True,
            )
        with col_c:
            st.metric("Trip readiness", f"{scores.trip_readiness_score:.0f}/100")
            st.markdown(
                score_badge("Trip readiness", scores.trip_readiness_score),
                unsafe_allow_html=True,
            )
        with col_d:
            if getattr(scores, "crowd_score", None) is not None:
                st.metric("Crowd score", f"{scores.crowd_score:.0f}/100")
                st.markdown(
                    score_badge("Crowd score", scores.crowd_score),
                    unsafe_allow_html=True,
                )

        if scores.risk_flags:
            st.markdown("**Risk flags:** " + ", ".join(sorted(scores.risk_flags)))
        else:
            st.markdown("**Risk flags:** none")

        if scores.notes:
            with st.expander("Score notes"):
                for note in scores.notes:
                    st.write(f"- {note}")

        # --- Weather table ---------------------------------------------------
        st.subheader("Weather forecast")

        if weather_days:
            rows = []
            for d in weather_days:  # type: ignore
                # Base metric fields from WeatherDay
                temp_max_c = getattr(d, "temp_max_c", None)
                temp_min_c = getattr(d, "temp_min_c", None)
                precip_prob = getattr(d, "precip_probability", None)  # 0–1
                wind_mps = getattr(d, "wind_speed_max_mps", None)

                # Derive US-friendly values
                high_f = None
                low_f = None
                if temp_max_c is not None:
                    high_f = temp_max_c * 9.0 / 5.0 + 32.0
                if temp_min_c is not None:
                    low_f = temp_min_c * 9.0 / 5.0 + 32.0

                precip_pct = None
                if precip_prob is not None:
                    precip_pct = precip_prob * 100.0

                wind_mph = None
                if wind_mps is not None:
                    wind_mph = wind_mps * 2.23694  # m/s -> mph

                rows.append(
                    {
                        "Date": d.date,
                        "High (°F)": round(high_f) if high_f is not None else None,
                        "Low (°F)": round(low_f) if low_f is not None else None,
                        "Precip (%)": round(precip_pct)
                        if precip_pct is not None
                        else None,
                        "Wind (mph)": round(wind_mph)
                        if wind_mph is not None
                        else None,
                        "Heat risk": getattr(d, "heat_index_risk", None),
                        "Storm risk": getattr(d, "storm_risk", None),
                    }
                )

            df_weather = pd.DataFrame(rows)
            st.dataframe(df_weather, hide_index=True)
        else:
            st.write("No weather data available for this trip window.")

        # --- NPS alerts list -------------------------------------------------
        st.subheader("NPS alerts")

        if alerts:
            for a in alerts:  # type: ignore
                st.markdown(f"**[{a.category}] {a.title}**")
                if getattr(a, "summary", None):
                    st.write(a.summary)
                if getattr(a, "url", None):
                    st.markdown(f"[More info]({a.url})")
                st.markdown("---")
        else:
            st.write("No active alerts found.")

        # --- Explanation -----------------------------------------------------
        st.subheader("Advisor explanation")
        st.write(explanation)

        # --- Debug: full prompt ----------------------------------------------
        ##got rid of for now

if __name__ == "__main__":
    main()
