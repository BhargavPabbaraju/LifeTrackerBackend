from abc import ABC, abstractmethod
from django.db.models import TextChoices
from enum import Enum

class ProgressType(Enum):
    BOOLEAN = "boolean" # Done or not done
    QUANTITY = "quantity" # positive number (hours, minutes, topics, etc)
    NUMERIC = "numeric" # float number (can be 0.5 hours, etc)
    PERCENTAGE = "percentage" # number between 0 to 100

class GoalType(TextChoices):
    STUDY_DAILY = "study_daily", "Study Daily"
    STUDY_HOURS = "study_hours", "Study Hours"



class BaseGoalType(ABC):
    name:str = "base"
    description:str = "Base Goal type"
    progress_type: ProgressType = ProgressType.BOOLEAN

    @classmethod
    @abstractmethod
    def required_goal_data(cls) -> dict:
        """Returns a dict describing the fields required in goal_data for this goal type"""
        pass

    @classmethod
    @abstractmethod
    def required_progress_data(cls) -> dict:
        """Returns a dict describing the fields required in progress_data of the tracker for this goal type"""
        pass
    
    @classmethod
    @abstractmethod
    def help_text(cls) -> str:
        """Help text for the frontend when creating a goal of this type"""
        pass

    @classmethod
    @abstractmethod
    def progress(cls) -> int | bool | float:
        """Actual progress of a single tracker mapped according to progress type"""
        pass


class StudyDaily(BaseGoalType):
    name = "study_daily"
    description = "Study every day for the period"
    progress_type = ProgressType.BOOLEAN # Whether studied for that day or not

    @classmethod
    def calculate_progress(cls, goal):
        if not goal.trackers:
            return 0
        done_days = sum(1 for t in goal.trackers.all() if t.progress)
        total_days = goal.trackers.count()
        return done_days / total_days * 100
    
    @classmethod
    def required_goal_data(cls):
        return {}
    
    @classmethod
    def required_progress_data(cls):
        return {"studied": False}
    
    @classmethod
    def help_text(cls):
        return "Mark as done each day you study"
    
    @classmethod 
    def progress(cls, data):
        return bool(data.get("studied",False))

    


class StudyHours(BaseGoalType):
    name = "study_hours"
    description = "Study for x hours for the period"
    progress_type = ProgressType.NUMERIC # How many hours studied(can be float)

    @classmethod
    def calculate_progress(cls, goal):
        if not goal.trackers:
            return 0
        goal_hours = goal.goal_data.get("hours", 0)
        actual_hours = sum(t.progress for t in goal.trackers.all())
        return min(actual_hours / goal_hours *100, 100)

    @classmethod
    def required_goal_data(cls):
        return {"hours": 0.0}
    
    @classmethod
    def required_progress_data(cls):
        return {"hours":0.0}
    
    @classmethod
    def help_text(cls):
        return "Mark how many hours studied"
    
    @classmethod 
    def progress(cls, data):
        return data.get("hours",0)


GOAL_TYPE_CLASSES = {
    "study_daily" : StudyDaily,
    "study_hours": StudyHours
}