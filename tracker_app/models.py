from datetime import date, timedelta
import calendar

from django.core.exceptions import ValidationError
from django.db import models

from .goal_types import GOAL_TYPE_CLASSES, GoalType


# This can be subjects, specific food names, etc
class Domain(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


# This can be Food, Chores, Learning, etc
class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Goal(models.Model):
    domain = models.ForeignKey(to=Domain, on_delete=models.CASCADE, related_name="week_goals")
    tags = models.ManyToManyField(to=Tag, related_name="goals", blank=True)

    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(blank=True, null=True)
    week = models.PositiveSmallIntegerField(blank=True, null=True)
    quarter = models.PositiveSmallIntegerField(blank=True, null=True)

    description = models.TextField()  # What exactly must be/was achieved

    goal_type = models.CharField(max_length=100, choices=GoalType.choices)
    goal_data = models.JSONField(blank=True, null=True)

    class Meta:
        unique_together = ("domain", "year", "month", "week", "quarter")

    @property
    def goal_type_instance(self):
        """
        Returns the GoalType class instance corresponding to this goal_type string
        """
        return GOAL_TYPE_CLASSES.get(self.goal_type)

    def clean(self):
        goal_type_instance = self.goal_type_instance
        if goal_type_instance:
            missing_fields = [
                f
                for f in goal_type_instance.required_goal_data()
                if f not in (self.goal_data or {})
            ]
            if missing_fields:
                raise ValidationError(f"Missing required goal data:{missing_fields}")

    def calculate_period_dates(self):
        y, m, w, q = self.year, self.month, self.week, self.quarter

        if self.quarter:
            start_month = (q - 1) * 3 + 1
            end_month = start_month + 2
            self.start_date = date(y, start_month, 1)
            last_day = calendar.monthrange(y, end_month)[1]
            self.end_date = date(y, end_month, last_day)

        elif self.month and self.week:
            # Week 1 starts on 1st of the month and 7 day chunks from there
            first_of_month = date(y, m, 1)
            start = first_of_month + timedelta(days=(w - 1) * 7)
            end = min(start + timedelta(days=6), date(y, m, calendar.monthrange(y, m)[1]))
            self.start_date, self.end_date = start, end

        elif self.month:
            self.start_date = date(y, m, 1)
            last_day = calendar.monthrange(y, m)[1]
            self.end_date = date(y, m, last_day)

        else:
            self.start_date = date(y, 1, 1)
            self.end_date = date(y, 12, 31)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(args, kwargs)


class Review(models.Model):
    domain = models.ForeignKey(
        to=Domain, on_delete=models.CASCADE, related_name="reviews", blank=True
    )

    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(blank=True, null=True)
    week = models.PositiveSmallIntegerField(blank=True, null=True)
    quarter = models.PositiveSmallIntegerField(blank=True, null=True)

    # Optional notes / reflections / adjustments
    notes = models.TextField(blank=True, null=True)
    adjustments = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("domain", "year", "month", "week", "quarter")

    def average_progress(self):
        trackers = Tracker.objects.filter(domain=self.domain, date__year=self.year)
        if self.month:
            trackers = trackers.filter(date__month=self.month)
        if self.week:
            trackers = trackers.filter(date__week=self.week)
        if self.quarter:
            start_month = (self.quarter - 1) * 3 + 1
            end_month = start_month + 2
            trackers = trackers.filter(
                date__year=self.year, date__month__range=(start_month, end_month)
            )

        total = trackers.count()
        if not total:
            return 0
        return sum(t.progress or 0 for t in trackers) / total


class Schedule(models.Model):
    goal = models.ForeignKey(to=Goal, on_delete=models.CASCADE, related_name="schedules")
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)

    def __str__(self):
        return f"{self.goal.description} - {self.date}"


class Tracker(models.Model):
    class TrackerStatuses(models.TextChoices):
        PLANNED = "planned", "Planned"
        DONE = "done", "Done"
        PARTIAL = "partial", "Partial"
        SKIPPED = "skipped", "Skipped"

    goal = models.ForeignKey(
        to=Goal, blank=True, null=True, on_delete=models.SET_NULL, related_name="trackers"
    )
    schedule = models.ForeignKey(
        to=Schedule, blank=True, null=True, on_delete=models.SET_NULL, related_name="trackers"
    )
    domain = models.ForeignKey(to=Domain, on_delete=models.CASCADE, related_name="trackers")
    tags = models.ManyToManyField(to=Tag, related_name="trackers", blank=True)

    date = models.DateField()
    description = models.TextField()  # What exactly must be/was achieved

    planned_start_time = models.TimeField(blank=True, null=True)
    planned_duration = models.DurationField(blank=True, null=True)

    actual_start_time = models.TimeField(blank=True, null=True)
    actual_duration = models.DurationField(blank=True, null=True)

    progress_data = models.JSONField(blank=True, null=True)
    status = models.CharField(choices=TrackerStatuses, default=TrackerStatuses.PLANNED)

    def clean(self):
        if not self.goal or not self.goal.goal_type_instance:
            return
        goal_type_instance = self.goal.goal_type_instance
        if goal_type_instance:
            missing_fields = [
                f
                for f in goal_type_instance.required_progress_data()
                if f not in (self.progress_data or {})
            ]
            if missing_fields:
                raise ValidationError(f"Missing required goal data:{missing_fields}")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(args, kwargs)

    @property
    def all_tags(self):
        return set(self.goal.tags.all() if self.goal else {}).union(set(self.tags.all()))

    @property
    def progress(self):
        if not self.goal or not self.goal.goal_type_instance:
            return None
        return self.goal.goal_type_instance.progress(self.progress_data or {})
