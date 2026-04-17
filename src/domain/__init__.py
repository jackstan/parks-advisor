"""
Domain layer: objective-oriented models and constraints.

This module defines the core concept of an "Objective" — the thing being evaluated.
It's domain-agnostic; specific domains (climbing, hiking, skiing) extend these models.
"""

from .objective_models import Objective, UserConstraints, ObjectiveRecommendation

__all__ = ["Objective", "UserConstraints", "ObjectiveRecommendation"]
