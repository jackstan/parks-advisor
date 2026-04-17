#!/usr/bin/env python3
"""
Quick validation test for the planner orchestrator.
"""

from datetime import datetime, timedelta
from src.domain.recommendation_models import RecommendationRequest
from src.orchestration import plan_outdoor_objective

# Test 1: Climbing planning
print("=" * 60)
print("TEST 1: Climbing Planning")
print("=" * 60)

today = datetime.now().date()
tomorrow = today + timedelta(days=1)

climbing_request = RecommendationRequest(
    domain="climbing",
    location_ids=["rrg"],  # Red River Gorge
    start_date=str(today),
    end_date=str(tomorrow),
    grade_min="5.8",
    grade_max="5.11a",
    max_duration_hours=4.0,
    max_approach_minutes=30,
    skill_level="intermediate",
)

try:
    climbing_rec = plan_outdoor_objective(climbing_request)
    print(f"✓ Climbing recommendation generated")
    print(f"  Verdict: {climbing_rec.sendability_verdict}")
    print(f"  Score: {climbing_rec.overall_sendability_score:.1f}")
    print(f"  Primary: {climbing_rec.primary_objective.location_name}")
    print(f"  Backup: {climbing_rec.backup_objective.location_name}")
    print(f"  Explanation: {climbing_rec.short_explanation}")
except Exception as e:
    print(f"✗ Climbing planning failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Hiking planning
print("\n" + "=" * 60)
print("TEST 2: Hiking Planning")
print("=" * 60)

hiking_request = RecommendationRequest(
    domain="hiking",
    location_ids=["yose"],  # Yosemite
    start_date=str(today),
    end_date=str(tomorrow),
    max_duration_hours=6.0,
    skill_level="intermediate",
)

try:
    hiking_rec = plan_outdoor_objective(hiking_request)
    print(f"✓ Hiking recommendation generated")
    print(f"  Verdict: {hiking_rec.sendability_verdict}")
    print(f"  Score: {hiking_rec.overall_sendability_score:.1f}")
    print(f"  Primary: {hiking_rec.primary_objective.location_name}")
    print(f"  Backup: {hiking_rec.backup_objective.location_name}")
    print(f"  Explanation: {hiking_rec.short_explanation}")
except Exception as e:
    print(f"✗ Hiking planning failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
