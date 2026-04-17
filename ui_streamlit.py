import datetime as dt
from typing import Dict, List

import pandas as pd
import pydeck as pdk
import streamlit as st

from src.config import get_locations_by_domain
from src.domain.recommendation_models import (
    DayPlan,
    ObjectiveCandidate,
    PlannerRecommendation,
    RecommendationRequest,
)
from src.orchestration import plan_outdoor_objective


GRADE_OPTIONS = [
    "5.6",
    "5.7",
    "5.8",
    "5.9",
    "5.10a",
    "5.10b",
    "5.10c",
    "5.10d",
    "5.11a",
    "5.11b",
    "5.11c",
    "5.11d",
    "5.12a",
    "5.12b",
    "5.12c",
    "5.12d",
    "5.13a",
    "5.13b",
]


def verdict_badge(verdict: str, score: float) -> str:
    """Render the sendability status badge."""
    verdict = verdict.upper()
    if verdict == "GO":
        bg = "#dcfce7"
        fg = "#166534"
        label = "Send"
    elif verdict == "CAUTION":
        bg = "#fef3c7"
        fg = "#92400e"
        label = "Caution"
    else:
        bg = "#fee2e2"
        fg = "#991b1b"
        label = "Hold"

    return (
        f"<div style='display:inline-block;padding:0.4rem 0.75rem;border-radius:999px;"
        f"background:{bg};color:{fg};font-weight:700;font-size:0.95rem;'>"
        f"{label} window · {score:.0f}/100"
        f"</div>"
    )


def pretty_label(value: str) -> str:
    """Convert snake_case values into UI copy."""
    return value.replace("_", " ").strip().title()


def parse_objective_text(value: str) -> List[str]:
    """Parse free-form objective input into a clean list of search terms."""
    parsed: List[str] = []
    seen: set[str] = set()

    normalized = value.replace("\n", ",")
    for part in normalized.split(","):
        candidate = part.strip()
        key = candidate.lower()
        if not candidate or key in seen:
            continue
        seen.add(key)
        parsed.append(candidate)

    return parsed


def summarize_objective(candidate: ObjectiveCandidate) -> List[str]:
    """Build a short metadata summary for the objective."""
    metadata = candidate.location_metadata or {}
    parts: List[str] = []

    if candidate.objective.domain == "climbing":
        climb_types = metadata.get("primary_climb_types") or []
        if climb_types:
            parts.append(f"Styles: {', '.join(climb_types)}")
        if metadata.get("primary_rock_type"):
            parts.append(f"Rock: {metadata['primary_rock_type']}")
        if metadata.get("grade_range"):
            parts.append(f"Grades: {metadata['grade_range']}")
        if metadata.get("distance_miles") is not None:
            parts.append(f"Distance: {metadata['distance_miles']} miles from origin")
        if candidate.route_options:
            parts.append(f"Route options: {len(candidate.route_options)}")
    else:
        if metadata.get("states"):
            parts.append(f"State: {', '.join(metadata['states'])}")
        if metadata.get("season_notes"):
            parts.append(f"Season note: {metadata['season_notes']}")

    return parts


def build_map_dataframe(recommendation: PlannerRecommendation) -> pd.DataFrame:
    """Convert planner map points to a dataframe for pydeck."""
    rows = []
    for point in recommendation.map_points:
        if point.role == "primary":
            color = [22, 101, 52, 220]
            radius = 48000
            role_label = "Primary objective"
        else:
            color = [180, 83, 9, 220]
            radius = 36000
            role_label = "Backup objective"

        rows.append(
            {
                "label": point.label,
                "lat": point.lat,
                "lon": point.lon,
                "score": f"{point.score:.0f}" if point.score is not None else "n/a",
                "role_label": role_label,
                "description": point.description or "",
                "color": color,
                "radius": radius,
            }
        )

    return pd.DataFrame(rows)


def compute_map_zoom(points: pd.DataFrame) -> float:
    """Choose a practical zoom level based on marker spread."""
    if points.empty:
        return 4.0

    lat_span = float(points["lat"].max() - points["lat"].min())
    lon_span = float(points["lon"].max() - points["lon"].min())
    span = max(lat_span, lon_span)

    if span > 25:
        return 2.8
    if span > 12:
        return 3.4
    if span > 6:
        return 4.2
    if span > 2:
        return 5.2
    return 6.2


def render_map(recommendation: PlannerRecommendation) -> None:
    """Render the recommendation map."""
    points = build_map_dataframe(recommendation)
    if points.empty:
        st.info("Map data is not available for this recommendation.")
        return

    center_lat = float(points["lat"].mean())
    center_lon = float(points["lon"].mean())
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=compute_map_zoom(points),
        pitch=0,
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=points,
        get_position="[lon, lat]",
        get_fill_color="color",
        get_radius="radius",
        pickable=True,
        stroked=True,
        get_line_color=[255, 255, 255, 220],
        line_width_min_pixels=2,
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_provider="carto",
        tooltip={
            "html": (
                "<b>{role_label}</b><br/>"
                "{label}<br/>"
                "Sendability: {score}/100<br/>"
                "{description}"
            )
        },
        map_style="light",
    )

    st.pydeck_chart(deck, use_container_width=True)
    st.caption("Green marks the primary objective. Amber marks the backup objective.")


def render_conditions(recommendation: PlannerRecommendation) -> None:
    """Render the conditions summary."""
    conditions = recommendation.conditions_summary or {}
    metric_cols = st.columns(4)
    metric_cols[0].metric("High", f"{conditions.get('temperature_f', 'n/a')} F")
    metric_cols[1].metric("Low", f"{conditions.get('temperature_low_f', 'n/a')} F")
    metric_cols[2].metric("Precip", f"{conditions.get('precipitation_probability', 'n/a')}%")
    metric_cols[3].metric("Wind", f"{conditions.get('wind_mph', 'n/a')} mph")

    detail_cols = st.columns(2)
    with detail_cols[0]:
        st.write(f"Rock / surface condition: **{pretty_label(str(conditions.get('rock_condition', 'unknown')))}**")
    with detail_cols[1]:
        st.write(f"Forecast confidence: **{pretty_label(str(conditions.get('forecast_confidence', 'unknown')))}**")


def render_score_breakdown(recommendation: PlannerRecommendation) -> None:
    """Render the score table."""
    scores = recommendation.sendability_scores or {}
    rows = [
        {"Dimension": pretty_label(name), "Score": f"{value:.0f}/100"}
        for name, value in scores.items()
        if value is not None
    ]
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_risks(recommendation: PlannerRecommendation) -> None:
    """Render the risk list."""
    if recommendation.risk_flags:
        for flag in recommendation.risk_flags:
            st.write(f"- {pretty_label(flag)}")
    else:
        st.write("No major risks were flagged for the current window.")


def render_plan(plan_title: str, candidate: ObjectiveCandidate, plan: DayPlan) -> None:
    """Render an objective plan card."""
    st.markdown(f"#### {plan_title}")
    st.write(f"**{candidate.location_name}**")
    st.write(candidate.selection_reason or candidate.match_reason)

    for line in summarize_objective(candidate):
        st.caption(line)

    info_cols = st.columns(3)
    info_cols[0].metric("Score", f"{candidate.overall_sendability_score:.0f}/100")
    info_cols[1].metric("Start", plan.start_time)
    info_cols[2].metric("Approach", f"{plan.approach_minutes} min")

    st.write(f"Window: **{plan.day}**")
    st.write(f"Plan length: **{plan.expected_duration_hours:.1f} hours**")
    st.write("Itinerary:")
    for item in plan.routes_or_trails:
        st.write(f"- {item}")
    st.write(f"Gear: **{plan.gear_required}**")
    st.write(f"Conditions note: {plan.weather_specific_notes}")

    if candidate.scores and candidate.scores.notes:
        with st.expander("Why this was selected"):
            for note in candidate.scores.notes[:5]:
                st.write(f"- {note}")


def build_request(
    domain: str,
    start_date: dt.date,
    end_date: dt.date,
    location_ids: List[str],
    skill_level: str,
    max_duration_hours: float,
    max_approach_minutes: int,
    commitment_level: str,
    partner_count: int,
    grade_min: str | None,
    grade_max: str | None,
    custom_notes: str | None,
) -> RecommendationRequest:
    """Translate UI values into the planner request."""
    return RecommendationRequest(
        domain=domain,
        location_ids=location_ids or None,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        grade_min=grade_min,
        grade_max=grade_max,
        max_duration_hours=max_duration_hours,
        max_approach_minutes=max_approach_minutes,
        commitment_level=commitment_level,
        skill_level=skill_level,
        partner_count=partner_count if domain == "climbing" else None,
        custom_notes=(custom_notes or "").strip() or None,
    )


def planner_form() -> RecommendationRequest | None:
    """Render the sidebar form and return a request when submitted."""
    today = dt.date.today()
    max_forecast_day = today + dt.timedelta(days=16)

    with st.sidebar:
        st.header("Planner Inputs")
        st.caption("Climbing-first for v1, with the same planner shape ready for future domains.")

        with st.form("sendable_planner"):
            domain = st.selectbox("Domain", ["climbing", "hiking"], index=0)
            location_options: Dict[str, str] = get_locations_by_domain(domain)

            start_date = st.date_input(
                "Start date",
                value=today + dt.timedelta(days=2),
                min_value=today,
                max_value=max_forecast_day,
            )
            end_date = st.date_input(
                "End date",
                value=today + dt.timedelta(days=3),
                min_value=start_date,
                max_value=max_forecast_day,
            )

            freeform_objectives = ""
            selected_seed_objectives: List[str] = []
            if domain == "climbing":
                freeform_objectives = st.text_area(
                    "Objective ideas",
                    placeholder="Smith Rock\nYosemite National Park\nSan Francisco",
                    help=(
                        "Enter climbing destinations or origin cities in free form. Use one per line or "
                        "comma-separated names. Destination searches expand into route-bearing crags; "
                        "origin searches surface nearby climbing."
                    ),
                )
                selected_seed_objectives = st.multiselect(
                    "Quick picks",
                    options=list(location_options.keys()),
                    format_func=lambda code: location_options[code],
                    help="Optional seeded areas you want included alongside free-form search terms.",
                )
            else:
                selected_seed_objectives = st.multiselect(
                    "Preferred objectives",
                    options=list(location_options.keys()),
                    format_func=lambda code: location_options[code],
                    help="Leave blank to let Sendable rank all known options in this domain.",
                )

            skill_level = st.selectbox(
                "Skill level",
                ["beginner", "intermediate", "advanced"],
                index=1,
            )

            max_duration_hours = st.slider(
                "Max day length (hours)",
                min_value=2.0,
                max_value=12.0,
                value=6.0 if domain == "hiking" else 5.0,
                step=0.5,
            )

            max_approach_minutes = st.slider(
                "Max approach (minutes)",
                min_value=5,
                max_value=180,
                value=30,
                step=5,
            )

            commitment_level = st.selectbox(
                "Commitment",
                ["flexible", "walk-up", "half-day", "full-day", "multi-day"],
                index=0,
            )

            custom_notes = st.text_area(
                "Notes",
                placeholder="Optional details like route goals, style preferences, partner constraints, or timing notes.",
                help="This goes into the planner request as extra context without changing the core objective search.",
            )

            grade_min = None
            grade_max = None
            partner_count = 2
            if domain == "climbing":
                grade_cols = st.columns(2)
                with grade_cols[0]:
                    grade_min = st.selectbox("Min grade", GRADE_OPTIONS, index=2)
                with grade_cols[1]:
                    grade_max = st.selectbox("Max grade", GRADE_OPTIONS, index=8)
                partner_count = st.number_input(
                    "Partner count",
                    min_value=1,
                    max_value=4,
                    value=2,
                    step=1,
                )

            submitted = st.form_submit_button("Build Plan", use_container_width=True)

        if not submitted:
            return None

        if domain == "climbing":
            if GRADE_OPTIONS.index(grade_max) < GRADE_OPTIONS.index(grade_min):
                st.error("Max grade must be at or above the minimum grade.")
                return None

        if end_date < start_date:
            st.error("End date must be on or after the start date.")
            return None

        location_ids = selected_seed_objectives
        if domain == "climbing":
            freeform_location_ids = parse_objective_text(freeform_objectives)
            combined = list(location_ids)
            existing = {item.lower() for item in combined}
            for item in freeform_location_ids:
                if item.lower() not in existing:
                    combined.append(item)
                    existing.add(item.lower())
            location_ids = combined

        return build_request(
            domain=domain,
            start_date=start_date,
            end_date=end_date,
            location_ids=location_ids,
            skill_level=skill_level,
            max_duration_hours=max_duration_hours,
            max_approach_minutes=max_approach_minutes,
            commitment_level=commitment_level,
            partner_count=partner_count,
            grade_min=grade_min,
            grade_max=grade_max,
            custom_notes=custom_notes,
        )


def render_recommendation(recommendation: PlannerRecommendation) -> None:
    """Render the main planner result."""
    st.markdown("### Sendability Status")
    status_cols = st.columns([1.2, 0.9, 0.9])
    with status_cols[0]:
        st.markdown(
            verdict_badge(
                recommendation.sendability_verdict,
                recommendation.overall_sendability_score,
            ),
            unsafe_allow_html=True,
        )
        st.write(recommendation.short_explanation)
    with status_cols[1]:
        st.metric("Primary objective", recommendation.primary_objective.location_name)
    with status_cols[2]:
        st.metric("Backup objective", recommendation.backup_objective.location_name)

    st.markdown("### Objective Map")
    render_map(recommendation)

    st.markdown("### Objective Decision")
    objective_cols = st.columns(2)
    with objective_cols[0]:
        render_plan("Primary Objective", recommendation.primary_objective, recommendation.primary_plan)
    with objective_cols[1]:
        render_plan("Backup Objective", recommendation.backup_objective, recommendation.backup_plan)

    st.markdown("### Conditions Summary")
    render_conditions(recommendation)

    detail_cols = st.columns(2)
    with detail_cols[0]:
        st.markdown("#### Risks")
        render_risks(recommendation)
    with detail_cols[1]:
        st.markdown("#### Score Breakdown")
        render_score_breakdown(recommendation)


def main() -> None:
    st.set_page_config(
        page_title="Sendable",
        page_icon="S",
        layout="wide",
    )

    st.title("Sendable")
    st.write(
        "A climbing-first objective planner that helps you decide what is actually sendable, "
        "what the backup should be, and where the recommendation sits on the map."
    )
    st.caption(
        "This v1 UI keeps the current Streamlit stack, but shifts the experience from a generic "
        "advisor into a compact decision tool."
    )

    request = planner_form()
    if request is None:
        st.info(
            "Set a trip window and optional preferred objectives in the sidebar, then build a plan. "
            "The output will show sendability, primary and backup objectives, why they were chosen, "
            "conditions, risks, itinerary details, and a map."
        )
        return

    with st.spinner("Ranking objective windows and building the plan..."):
        try:
            recommendation = plan_outdoor_objective(request)
        except Exception as exc:
            st.error(f"Planner run failed: {exc}")
            return

    render_recommendation(recommendation)


if __name__ == "__main__":
    main()
