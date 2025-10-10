from django.contrib import admin

from .models import *

# Register your models here.


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]


class ScheduleInline(admin.TabularInline):
    model = Schedule
    extra = 1
    min_num = 1
    fields = ("recurrence", "weekday", "week_order", "day", "start_time", "duration")
    show_change_link = True


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["id", "domain", "description", "year", "month", "week", "quarter", "goal_type"]
    filter_horizontal = ["tags"]
    inlines = [ScheduleInline]


@admin.register(Tracker)
class TrackerAdmin(admin.ModelAdmin):
    list_display = ["id", "domain", "date", "goal"]
    filter_horizontal = ["tags"]
