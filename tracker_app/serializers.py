from rest_framework import serializers
from .models import *

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['id','name']
    
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id','name']

class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = [
            'id','weekday','week_order','day',
            'start_time','duration','recurrence'
        ]

class GoalSerializer(serializers.ModelSerializer):
    schedules = ScheduleSerializer(many=True)

    class Meta:
        model = Goal
        fields = [
            'id','domain','tags','year','month','week','quarter',
            'description','goal_type','goal_data','schedules'
        ]
    
    def create(self, validated_data):
        schedules_data = validated_data.pop('schedules',[])
        goal = Goal.objects.create(**validated_data)

        for schedule_data in schedules_data:
            Schedule.objects.create(goal=goal,**schedule_data)
        
        return goal

    def update(self, instance, validated_data):
        schedules_data = validated_data.pop('schedules',None)
        
        for attr,value in validated_data.items():
            setattr(instance,attr,value)
        instance.save()

        if schedules_data is not None:
            instance.schedules.all().delete()
            for schedule_data in schedules_data:
                Schedule.objects.create(goal=instance,**schedule_data)
        
        return instance

