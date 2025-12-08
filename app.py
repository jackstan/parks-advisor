from src.models import TripRequest
from src.advisor_llm import advise_trip_with_explanation
from datetime import date, timedelta

def main():
    today = date.today()
    # Keep the trip within the next 10 days so Open-Meteo can give real forecasts
    start = today + timedelta(days=3)
    end = start + timedelta(days=2)

    trip = TripRequest(
        park_code="yose",
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        activity_type="hiking",
        hiker_profile="intermediate",
        constraints={"max_hike_hours": 6},
    )

    scores, explanation, prompt_debug = advise_trip_with_explanation(trip)

    print("=== Scores ===")
    print(scores)

    print("\n=== Explanation (stub) ===")
    print(explanation)

    print("\n=== Prompt Debug (first 2000 chars) ===")
    print(prompt_debug[:2000])


if __name__ == "__main__":
    main()



