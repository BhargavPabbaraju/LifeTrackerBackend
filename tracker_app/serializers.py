from rest_framework import serializers

from .goal_types import ProgressType
from .models import *


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ["id", "name"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = ["id", "date", "start_time", "duration", "description", "goal_context"]


class GoalTypeSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField()
    progress_type = serializers.CharField()
    required_goal_data = serializers.DictField()
    required_schedule_data = serializers.DictField()
    required_progress_data = serializers.DictField()
    help_text = serializers.CharField()

    def to_representation(self, instance):
        return {
            "name": instance.name,
            "description": instance.description,
            "progress_type": (
                instance.progress_type.value
                if isinstance(instance.progress_type, ProgressType)
                else instance.progress_type
            ),
            "required_goal_data": instance.required_goal_data(),
            "required_schedule_data": instance.required_schedule_data(),
            "required_progress_data": instance.required_progress_data(),
            "help_text": instance.help_text(),
        }


class GoalSerializer(serializers.ModelSerializer):
    schedules = ScheduleSerializer(many=True)

    class Meta:
        model = Goal
        fields = [
            "id",
            "domain",
            "tags",
            "year",
            "month",
            "week",
            "quarter",
            "description",
            "goal_type",
            "goal_data",
            "schedules",
        ]

    def create(self, validated_data):
        schedules_data = validated_data.pop("schedules", [])
        goal = Goal.objects.create(**validated_data)

        for schedule_data in schedules_data:
            Schedule.objects.create(goal=goal, **schedule_data)

        return goal

    def update(self, instance, validated_data):
        schedules_data = validated_data.pop("schedules", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if schedules_data is not None:
            instance.schedules.all().delete()
            for schedule_data in schedules_data:
                Schedule.objects.create(goal=instance, **schedule_data)

        return instance
