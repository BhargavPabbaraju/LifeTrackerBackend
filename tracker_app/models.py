from datetime import date, timedelta
import calendar

from django.core.exceptions import ValidationError
from django.db import models

from .goal_types import GOAL_TYPE_CLASSES, GoalType


def validate_schema_data(provided: dict, schema: dict, label: str):
    missing_fields = [
        field_name
        for field_name, field_def in schema.items()
        if field_def.get("required", True) and field_name not in (provided or {})
    ]
    if missing_fields:
        raise ValidationError({label: f"Missing required fields: {missing_fields}"})


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
        if self.goal_type_instance:
            validate_schema_data(
                self.goal_data, self.goal_type_instance.required_goal_data(), "goal_data"
            )

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
        super().save(*args, **kwargs)


class GoalReview(models.Model):
    goal = models.OneToOneField(to=Goal, on_delete=models.CASCADE, related_name="review")
    notes = models.TextField(blank=True, null=True)
    reflections = models.TextField(blank=True, null=True)
    overall_progress = models.FloatField(default=0)
    carry_over_notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_progress(self):
        if not self.goal or not self.goal.goal_type_instance:
            return 0
        return self.goal.goal_type_instance.calculate_progress(self.goal)

    def save(self, *args, **kwargs):
        self.overall_progress = self.calculate_progress()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Review for {self.goal.description[:40]} ({self.overall_progress:.1f}%)"


class DomainReview(models.Model):
    domain = models.ForeignKey(to=Domain, on_delete=models.CASCADE, related_name="reviews")

    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(blank=True, null=True)
    week = models.PositiveSmallIntegerField(blank=True, null=True)
    quarter = models.PositiveSmallIntegerField(blank=True, null=True)

    notes = models.TextField(blank=True, null=True)
    reflections = models.TextField(blank=True, null=True)
    summary_progress = models.FloatField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("domain", "year", "month", "week", "quarter")

    def average_progress(self):
        goals = Goal.objects.filter(domain=self.domain, year=self.year)
        if self.month:
            goals = goals.filter(month=self.month)
        if self.week:
            goals = goals.filter(week=self.week)
        if self.quarter:
            goals = goals.filter(quarter=self.quarter)

        reviews = GoalReview.objects.filter(goal__in=goals)
        if not reviews.exists():
            return 0
        return sum(r.overall_progress for r in reviews) / reviews.count()

    def save(self, *args, **kwargs):
        self.summary_progress = self.average_progress()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.domain.name} Review ({self.year}-{self.month or self.quarter})"


class ScheduleRule(models.Model):
    class Recurrence(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    goal = models.ForeignKey(to=Goal, on_delete=models.CASCADE, related_name="schedule_rules")

    frequency = models.CharField(
        choices=Recurrence.choices,
        default=Recurrence.DAILY,
        help_text="How often the schedule repeats (daily/weekly/monthly).",
    )
    interval = models.PositiveSmallIntegerField(
        default=1, help_text="Repeat every N units (days/weeks/months)."
    )

    # For weekly recurrence (0=Monday, 6=Sunday)
    weekdays = models.JSONField(default=list, blank=True)

    # For monthly recurrence
    days = models.JSONField(default=list, blank=True, help_text="Specific days of the month.")
    week_order = models.JSONField(
        default=list, blank=True, help_text="Optional: nth weekdays for monthly recurrence."
    )

    # Descriptive / contextual fields
    description = models.TextField(
        help_text="What exactly must be achieved for this recurring block.",
        blank=True,
        null=True,
    )

    goal_context = models.JSONField(
        blank=True,
        null=True,
        help_text="Default goal-specific context for generated schedules (e.g. planned_hours, topic).",
    )

    # Scheduling defaults
    start_time = models.TimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)

    # Dates excluded from recurrence
    exceptions = models.JSONField(default=list, blank=True)

    def clean(self):
        if self.frequency == self.Recurrence.WEEKLY and not self.weekdays:
            raise ValidationError("Weekdays are required for weekly recurrence.")
        if self.frequency == self.Recurrence.MONTHLY and not (self.days or self.week_order):
            raise ValidationError("Days or week order required for monthly recurrence.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.goal} [{self.frequency} every {self.interval}]"

    def clean(self):
        goal_type_instance = self.goal.goal_type_instance if self.goal else None
        if goal_type_instance:
            validate_schema_data(
                self.goal_context, self.goal_type_instance.required_schedule_data(), "goal_context"
            )

    # def generated_dates(self, start_date, end_date):
    #     current = date(start_date.year, start_date.month, 1)
    #     while current <= end_date:
    #         _, days_in_month = calendar.monthrange(current.year, current.month)
    #         for pattern in self.week_order:
    #             week = pattern["week"]
    #             weekday = pattern["weekday"]  # 0=Mon .. 6=Sun

    #             if week > 0:
    #                 # nth weekday
    #                 first_day = date(current.year, current.month, 1)
    #                 first_weekday = first_day.weekday()
    #                 delta = (weekday - first_weekday + 7) % 7
    #                 target = first_day + timedelta(days=delta + 7 * (week - 1))
    #             else:
    #                 # last weekday (week=-1)
    #                 last_day = date(current.year, current.month, days_in_month)
    #                 last_weekday = last_day.weekday()
    #                 delta = (last_weekday - weekday + 7) % 7
    #                 target = last_day - timedelta(days=delta)

    #             if target.month == current.month and start_date <= target <= end_date:
    #                 yield target

    #         # move to next month
    #         current = date(current.year + (current.month // 12), (current.month % 12) + 1, 1)


# Each Schedule is tied to a single date, can either be manually selected or generated from a ScheduleRule
class Schedule(models.Model):
    goal = models.ForeignKey(to=Goal, on_delete=models.CASCADE, related_name="schedules")
    schedule_rule = models.ForeignKey(
        blank=True, null=True, to=ScheduleRule, on_delete=models.CASCADE, related_name="schedules"
    )
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    description = models.TextField(help_text="What exactly must be achieved", blank=True, null=True)
    goal_context = models.JSONField(
        blank=True,
        null=True,
        help_text="Per-day plan toward the goal (e.g., planned_hours, topic).",
    )

    def __str__(self):
        return f"{self.goal.description} - {self.date}"

    def clean(self):
        goal_type_instance = self.goal.goal_type_instance if self.goal else None
        if goal_type_instance:
            validate_schema_data(
                self.goal_context, self.goal_type_instance.required_schedule_data(), "goal_context"
            )


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
    description = models.TextField(
        help_text="What exactly must be/was achieved", blank=True, null=True
    )

    planned_start_time = models.TimeField(blank=True, null=True)
    planned_duration = models.DurationField(blank=True, null=True)

    actual_start_time = models.TimeField(blank=True, null=True)
    actual_duration = models.DurationField(blank=True, null=True)

    progress_data = models.JSONField(blank=True, null=True)
    status = models.CharField(choices=TrackerStatuses, default=TrackerStatuses.PLANNED)
    notes = models.TextField(blank=True, null=True)

    def clean(self):
        goal_type_instance = self.goal.goal_type_instance if self.goal else None
        if goal_type_instance:
            validate_schema_data(
                self.progress_data,
                self.goal_type_instance.required_progress_data(),
                "progress_data",
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def all_tags(self):
        return set(self.goal.tags.all() if self.goal else {}).union(set(self.tags.all()))

    @property
    def progress(self):
        if not self.goal or not self.goal.goal_type_instance:
            return None
        if not self.progress_data:
            return 0
        return self.goal.goal_type_instance.progress(self.progress_data)
