from abc import ABC, abstractmethod
from enum import Enum
from django.db.models import TextChoices


# --------------------------------------------
# Enums and Common Types
# --------------------------------------------


class ProgressType(Enum):
    BOOLEAN = "boolean"  # Done or not done
    QUANTITY = "quantity"  # positive number (pages, reps, etc.)
    NUMERIC = "numeric"  # float number (can be 0.5 hours, etc.)
    PERCENTAGE = "percentage"  # number between 0 and 100


class GoalType(TextChoices):
    STUDY_DAILY = "study_daily", "Study Daily"
    STUDY_HOURS = "study_hours", "Study Hours"


# --------------------------------------------
# Abstract Base
# --------------------------------------------


class BaseGoalType(ABC):
    """
    Base class for all goal types.
    Each subclass defines:
      - what data is needed at goal/schedule/tracker levels
      - how progress is measured and aggregated
    """

    name: str = "base"
    description: str = "Base Goal type"
    progress_type: ProgressType = ProgressType.BOOLEAN

    # ---------- Required Definitions ----------
    @classmethod
    @abstractmethod
    def required_goal_data(cls) -> dict:
        """Fields required in `goal_data` when creating the goal."""
        pass

    @classmethod
    @abstractmethod
    def required_schedule_data(cls) -> dict:
        """Fields required in `goal_context` when creating a schedule or rule."""
        pass

    @classmethod
    @abstractmethod
    def required_progress_data(cls) -> dict:
        """Fields required in `progress_data` when logging a tracker."""
        pass

    @classmethod
    @abstractmethod
    def help_text(cls) -> str:
        """Short help text for UI when creating this goal type."""
        pass

    @classmethod
    @abstractmethod
    def progress(cls, data) -> int | bool | float:
        """
        Compute progress for a single tracker instance
        based on its `progress_data`.
        """
        pass

    # ---------- Optional Utilities ----------
    @classmethod
    def schema(cls) -> dict:
        """Combined schema for frontend (goal/schedule/progress)."""
        return {
            "goal_type": cls.name,
            "description": cls.description,
            "progress_type": cls.progress_type.value,
            "required_goal_data": cls.required_goal_data(),
            "required_schedule_data": cls.required_schedule_data(),
            "required_progress_data": cls.required_progress_data(),
            "help_text": cls.help_text(),
        }

    @classmethod
    def calculate_progress(cls, goal):
        """Default aggregate: average of all tracker progress."""
        trackers = goal.trackers.all()
        if not trackers:
            return 0
        total = sum(t.progress or 0 for t in trackers)
        return total / len(trackers)


# --------------------------------------------
# Study Daily Goal Type
# --------------------------------------------


class StudyDaily(BaseGoalType):
    """
    Goal type: Study every day during the goal period.
    Progress = boolean (studied or not studied)
    """

    name = "study_daily"
    description = "Study every day for the period"
    progress_type = ProgressType.BOOLEAN

    @classmethod
    def required_goal_data(cls):
        # No setup data needed for this simple goal type
        return {}

    @classmethod
    def required_schedule_data(cls):
        # Optional topic or focus for that day
        return {
            "topic": {
                "type": "markdown",
                "label": "Study topic (optional)",
                "help": "What subject or topic to study this day?",
            }
        }

    @classmethod
    def required_progress_data(cls):
        return {
            "studied": {
                "type": "boolean",
                "label": "Did you study today?",
                "default": False,
            }
        }

    @classmethod
    def help_text(cls):
        return "Mark as done each day you study."

    @classmethod
    def progress(cls, data):
        # Boolean progress: True (1) or False (0)
        return bool(data.get("studied", False))

    @classmethod
    def calculate_progress(cls, goal):
        trackers = goal.trackers.all()
        if not trackers:
            return 0
        done_days = sum(1 for t in trackers if t.progress)
        return (done_days / trackers.count()) * 100


# --------------------------------------------
# Study Hours Goal Type
# --------------------------------------------


class StudyHours(BaseGoalType):
    """
    Goal type: Study for X hours within the goal period.
    Progress = numeric (sum of hours logged / target hours)
    """

    name = "study_hours"
    description = "Study for X hours during the selected period"
    progress_type = ProgressType.NUMERIC

    @classmethod
    def required_goal_data(cls):
        return {
            "hours": {
                "type": "number",
                "label": "Target hours",
                "help": "Total hours to study in the selected period",
                "min": 0,
                "step": 0.5,
                "unit": "hours",
            }
        }

    @classmethod
    def required_schedule_data(cls):
        return {
            "planned_hours": {
                "type": "number",
                "label": "Planned study hours",
                "help": "How many hours do you plan to study this day?",
                "min": 0,
                "step": 0.5,
                "unit": "hours",
            },
            "topic": {
                "type": "markdown",
                "label": "Study topic",
                "help": "What topic or subject will you study?",
            },
        }

    @classmethod
    def required_progress_data(cls):
        return {
            "hours": {
                "type": "number",
                "label": "Hours studied",
                "help": "How many hours did you actually study?",
                "min": 0,
                "step": 0.5,
                "unit": "hours",
            }
        }

    @classmethod
    def help_text(cls):
        return "Enter the number of hours studied for each day."

    @classmethod
    def progress(cls, data):
        # Returns numeric value (hours studied)
        return data.get("hours", 0.0)

    @classmethod
    def calculate_progress(cls, goal):
        trackers = goal.trackers.all()
        if not trackers:
            return 0
        goal_hours = goal.goal_data.get("hours", 0)
        actual_hours = sum(t.progress or 0 for t in trackers)
        if goal_hours <= 0:
            return 0
        return min(actual_hours / goal_hours * 100, 100)


class SpendLimit(BaseGoalType):
    name = "spend_limit"
    description = "Keep total spending under a defined limit"
    progress_type = ProgressType.NUMERIC  # sum of values

    @classmethod
    def required_goal_data(cls):
        return {
            "limit": {
                "type": "number",
                "label": "Spending limit ($)",
                "help": "Maximum allowed spending in the selected period",
                "min": 0,
                "step": 1,
                "unit": "$",
            },
            "category": {
                "type": "text",
                "label": "Spending category",
                "help": "Optional category like groceries, transport, etc.",
                "required": False,
            },
        }

    @classmethod
    def required_schedule_data(cls):
        # not applicable here
        return {}

    @classmethod
    def required_progress_data(cls):
        return {
            "spent": {
                "type": "number",
                "label": "Amount spent",
                "help": "How much did you spend for this log?",
                "min": 0,
                "step": 0.01,
                "unit": "$",
            }
        }

    @classmethod
    def progress(cls, data):
        # Each tracker just reports how much was spent
        return data.get("spent", 0)

    @classmethod
    def calculate_progress(cls, goal):
        trackers = goal.trackers.all()
        if not trackers:
            return 0
        limit = goal.goal_data.get("limit", 0)
        total_spent = sum(t.progress or 0 for t in trackers)
        # if progress = percentage of limit used:
        return min(total_spent / limit * 100, 100)


# --------------------------------------------
# Registry
# --------------------------------------------

GOAL_TYPE_CLASSES = {
    "study_daily": StudyDaily,
    "study_hours": StudyHours,
    "spend_limit": SpendLimit,
}
