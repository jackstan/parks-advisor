from src.models import TripRequest
from src.advisor import advise_trip

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

    scores, summary = advise_trip(trip)

    print("Scores:")
    print(scores)
    print("\nSummary:")
    print(summary)

if __name__ == "__main__":
    main()


