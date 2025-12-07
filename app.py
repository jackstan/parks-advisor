from src.models import TripRequest
from src.advisor_llm import advise_trip_with_explanation


def main():
    trip = TripRequest(
        park_code="yose",
        start_date="2025-06-15",
        end_date="2025-06-17",
        activity_type="hiking",
        hiker_profile="intermediate",
        trails_of_interest=["Mist Trail"],
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



