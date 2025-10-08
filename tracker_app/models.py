from datetime import time, timedelta

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
    class Recurrence(models.TextChoices):
        DAILY = "daily", "Daily"
        ONCE = "once", "Once"
        WEEKLY = "weekly", "Weekly"
        BIWEEKLY = "biweekly", "Biweekly"
        MONTHLY = "monthly", "Monthly"

    class Weekday(models.IntegerChoices):
        SUN = 0, "Sun"
        MON = 1, "Mon"
        TUE = 2, "Tue"
        WED = 3, "Wed"
        THU = 4, "Thu"
        FRI = 5, "Fri"
        SAT = 6, "Sat"

    goal = models.ForeignKey(to=Goal, on_delete=models.CASCADE, related_name="schedules")

    weekday = models.IntegerField(null=True, blank=True, choices=Weekday.choices)
    day = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="15 for 15th of the month"
    )
    week_order = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="2 for 2nd Wednesday of the month"
    )
    month = models.PositiveSmallIntegerField(
        choices=[(i, str(i)) for i in range(0, 13)],
        help_text="The month (1-12).",
        blank=True,
        null=True,
    )

    start_time = models.TimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    recurrence = models.CharField(max_length=20, choices=Recurrence.choices)

    def __str__(self):
        return f"{self.goal.description} - {self.recurrence}"

    def clean(self):
        """
        Custom validation logic that enforces valid combinations
        for each recurrence type.
        """
        # Common checks
        if self.duration and self.duration < timedelta(minutes=1):
            raise ValidationError("Duration must be at least one minute.")

        if self.start_time is not None:
            if not isinstance(self.start_time, time):
                raise ValidationError("Start time must be a valid time object.")

        if self.recurrence == self.Recurrence.DAILY:
            if any([self.week_order, self.weekday, self.day]):
                raise ValidationError(
                    "Daily recurrence should not specify weekday , day and week_order."
                )

        elif (
            self.recurrence == self.Recurrence.WEEKLY or self.recurrence == self.Recurrence.BIWEEKLY
        ):
            if self.week_order or self.day:
                raise ValidationError(
                    "Weekly and biweekly recurrence should not specify day and week_order."
                )
            if not self.weekday:
                raise ValidationError("Weekly and biweekly recurrence should specify weekday.")

        elif self.recurrence == self.Recurrence.MONTHLY:
            if not (self.day or (self.week_order and self.weekday)):
                raise ValidationError(
                    "Monthly recurrence must specify either a day or (week_order + weekday)."
                )

        elif self.recurrence == self.Recurrence.ONCE:
            if not (self.day or self.weekday or (self.week_order and self.weekday)):
                raise ValidationError(
                    "Either a day or a weekday or a (week_order + weekday) must be specified."
                )
        else:
            raise ValidationError("Unknown recurrence type")


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

    actual_starttime = models.TimeField(blank=True, null=True)
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
